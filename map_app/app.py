from flask import Flask, render_template, jsonify, request, make_response, send_from_directory
import pandas as pd
import numpy as np
import os
import io
import json
import secrets
import string
from utils.tmap_utils import create_matrix_from_locations
from utils.report_generator import generate_standalone_route_html
from dotenv import load_dotenv
from urllib.parse import urlencode, urlparse, parse_qs

# 환경변수 로드
load_dotenv()

app = Flask(__name__)

# 프로젝트 기반 파일 경로 설정
BASE_PROJECTS_DIR = 'projects'

def _sanitize_project_id(raw: str | None) -> str:
    """프로젝트 ID를 파일 시스템에 안전하도록 정규화합니다."""
    default_pid = 'default'
    if not raw:
        return default_pid
    # 영숫자, 하이픈, 언더스코어만 허용하고 나머지는 제거
    import re
    pid = re.sub(r'[^A-Za-z0-9_-]', '', str(raw))[:50]
    return pid if pid else default_pid

def get_project_id() -> str:
    """요청에서 projectId를 추출(쿼리/헤더/쿠키)하고 기본값은 'default'."""
    try:
        pid = request.args.get('projectId') or request.headers.get('X-Project-Id') or request.cookies.get('projectId')
    except Exception:
        pid = None
    return _sanitize_project_id(pid)


def generate_short_id(length: int = 4) -> str:
    """대문자 + 숫자로 이루어진 지정 길이의 안전한 랜덤 ID를 생성합니다.

    기본 길이는 4입니다 (예: 'A3Z7'). 소문자는 사용하지 않습니다.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def ensure_project_dir(project_id: str) -> str:
    """프로젝트 디렉터리를 보장하고 경로를 반환합니다."""
    proj_dir = os.path.join(BASE_PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    return proj_dir

def project_path(filename: str, project_id: str | None = None) -> str:
    """프로젝트 전용 파일 경로를 생성합니다."""
    pid = project_id or get_project_id()
    proj_dir = ensure_project_dir(pid)
    return os.path.join(proj_dir, filename)

def migrate_root_files_to_default():
    """루트에 있는 기존 파일들을 projects/default로 이동(최초 1회).
    이미 대상 경로에 있으면 이동하지 않음.
    """
    default_dir = ensure_project_dir('default')
    candidates = [
        'locations.csv',
        'time_matrix.csv',
        'distance_matrix.csv',
        'optimization_routes.csv',
        'optimization_summary.csv',
        'generated_routes.json',
        'route_metadata.json'
    ]
    for name in candidates:
        src = os.path.join(os.getcwd(), name)
        dst = os.path.join(default_dir, name)
        try:
            if os.path.exists(src) and not os.path.exists(dst):
                # 이동(원자적 rename 시도, 다른 파티션이면 copy 후 remove)
                try:
                    os.replace(src, dst)
                except Exception:
                    import shutil
                    shutil.copy2(src, dst)
                    os.remove(src)
                print(f"📦 Migrated '{name}' -> projects/default/{name}")
        except Exception as e:
            print(f"⚠️ Migration failed for {name}: {e}")

# 앱 시작 시 마이그레이션 수행
migrate_root_files_to_default()

# 프로젝트 목록 조회/생성 API
@app.route('/api/projects', methods=['GET'])
def list_projects():
    try:
        # 기본 프로젝트 디렉터리 보장
        ensure_project_dir('default')
        projects = []
        if not os.path.exists(BASE_PROJECTS_DIR):
            os.makedirs(BASE_PROJECTS_DIR, exist_ok=True)
        for name in os.listdir(BASE_PROJECTS_DIR):
            proj_dir = os.path.join(BASE_PROJECTS_DIR, name)
            if not os.path.isdir(proj_dir):
                continue
            loc_path = os.path.join(proj_dir, 'locations.csv')
            has_locations = os.path.exists(loc_path)
            count = 0
            try:
                if has_locations:
                    df = pd.read_csv(loc_path, encoding='utf-8-sig')
                    count = len(df)
            except Exception:
                pass
            projects.append({
                'id': name,
                'has_locations': has_locations,
                'location_count': int(count)
            })
        # 이름 기준 정렬(기본 default 우선)
        projects.sort(key=lambda x: (x['id'] != 'default', x['id']))
        return jsonify({'projects': projects})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    try:
        data = request.get_json(silent=True) or {}
        raw_id = data.get('projectId') or data.get('id')
        pid = _sanitize_project_id(raw_id)
        if not pid:
            return jsonify({'error': 'Invalid projectId'}), 400
        proj_dir = os.path.join(BASE_PROJECTS_DIR, pid)
        if os.path.exists(proj_dir):
            return jsonify({'error': 'Project already exists'}), 409
        os.makedirs(proj_dir, exist_ok=True)
        # 초기 locations.csv 생성(Depot 1개) - id는 문자열로 저장
        df = pd.DataFrame([
            {'id': '1', 'name': 'Depot', 'lon': 126.9779, 'lat': 37.5547, 'demand': 0}
        ], columns=['id', 'name', 'lon', 'lat', 'demand'])
        df.to_csv(os.path.join(proj_dir, 'locations.csv'), index=False, encoding='utf-8-sig')
        return jsonify({'created': True, 'id': pid}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def load_data(project_id: str | None = None):
    """CSV 파일에서 데이터를 로드합니다. 한글 인코딩을 자동으로 감지합니다."""
    locations_file = project_path('locations.csv', project_id)
    if os.path.exists(locations_file):
        # 다양한 인코딩 시도
        encodings_to_try = ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949']
        
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(locations_file, encoding=encoding)
                # 열 이름 공백 제거 및 불필요 열 제거
                df.columns = df.columns.str.strip()
                df = df.loc[:, ~df.columns.str.startswith('Unnamed')]

                # 중복 ID 컬럼(id.1 등) 처리
                if 'id.1' in df.columns:
                    if 'id' not in df.columns:
                        df['id'] = ''
                    df['id'] = df['id'].astype(str).replace({'nan': '', 'None': ''}).fillna('')
                    df['id.1'] = df['id.1'].astype(str).replace({'nan': '', 'None': ''}).fillna('')
                    empty_mask = df['id'].str.strip() == ''
                    df.loc[empty_mask, 'id'] = df.loc[empty_mask, 'id.1']
                    df = df.drop(columns=['id.1'])

                # 기대하는 열만 유지하고 부족한 열은 채워넣기
                expected_columns = ['id', 'name', 'lon', 'lat', 'demand']
                for col in expected_columns:
                    if col not in df.columns:
                        df[col] = np.nan
                df = df[expected_columns]

                # 데이터 타입 정규화
                df['id'] = df['id'].fillna('').astype(str)
                if 'name' in df.columns:
                    df['name'] = df['name'].fillna('').astype(str)
                if 'demand' in df.columns:
                    df['demand'] = pd.to_numeric(df['demand'], errors='coerce').fillna(0).astype(int)
                for coord_col in ('lon', 'lat'):
                    if coord_col in df.columns:
                        df[coord_col] = pd.to_numeric(df[coord_col], errors='coerce')

                # ID 중복/빈값 처리: 최초 로드 시에도 일관된 규칙 적용
                df['id'] = df['id'].fillna('').astype(str).str.strip()
                observed_ids: set[str] = set()
                empty_assigned = 0
                duplicate_sources: list[str] = []
                modified_ids = False

                for idx, current_id in df['id'].items():
                    if not current_id:
                        # 빈값 → Depot(첫 행)이면 '1', 나머지는 새 ID 부여
                        if idx == 0 and '1' not in observed_ids:
                            new_id = '1'
                        else:
                            new_id = None
                            attempts = 0
                            while attempts < 20:
                                candidate = generate_short_id(4)
                                if candidate not in observed_ids:
                                    new_id = candidate
                                    break
                                attempts += 1
                            if new_id is None:
                                # 예외적으로 모든 후보가 겹치면 UUID fallback
                                import uuid
                                new_id = uuid.uuid4().hex[:4].upper()
                        df.at[idx, 'id'] = new_id
                        observed_ids.add(new_id)
                        empty_assigned += 1
                        modified_ids = True
                        continue

                    if current_id in observed_ids:
                        # 중복 → 새로운 ID로 치환하되, 기존 값 기록
                        duplicate_sources.append(current_id)
                        new_id = None
                        attempts = 0
                        while attempts < 20:
                            candidate = generate_short_id(4)
                            if candidate not in observed_ids:
                                new_id = candidate
                                break
                            attempts += 1
                        if new_id is None:
                            import uuid
                            new_id = uuid.uuid4().hex[:4].upper()
                        df.at[idx, 'id'] = new_id
                        observed_ids.add(new_id)
                        modified_ids = True
                    else:
                        observed_ids.add(current_id)

                if duplicate_sources:
                    print(f"⚠️ locations.csv에서 중복된 ID를 감지하여 재할당했습니다: {duplicate_sources}")
                if empty_assigned:
                    print(f"ℹ️ locations.csv에 비어 있는 ID {empty_assigned}개에 랜덤 값을 부여했습니다.")
                if modified_ids:
                    try:
                        save_data(df, project_id)
                        print("💾 ID 정규화 결과를 locations.csv에 즉시 반영했습니다.")
                    except Exception as persist_error:
                        print(f"⚠️ ID 정규화 내용을 저장하지 못했습니다: {persist_error}")

                print(f"CSV 파일을 {encoding} 인코딩으로 로드했습니다.")
                return df
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"파일 로드 중 오류 ({encoding}): {e}")
                continue
        
        # 모든 인코딩 실패 시 기본 처리
        print("지원되는 인코딩으로 파일을 읽을 수 없습니다. 기본 DataFrame을 반환합니다.")
    
    return pd.DataFrame(columns=['id', 'name', 'lon', 'lat', 'demand'])

def save_data(df, project_id: str | None = None):
    """데이터를 CSV 파일에 저장합니다. UTF-8 인코딩으로 저장하여 한글 깨짐을 방지합니다."""
    try:
        locations_file = project_path('locations.csv', project_id)
        # UTF-8 BOM과 함께 저장하여 Excel에서도 한글이 정상 표시되도록 함
        df.to_csv(locations_file, index=False, encoding='utf-8-sig')
        print(f"데이터를 UTF-8-SIG 인코딩으로 저장했습니다.")
    except Exception as e:
        print(f"파일 저장 중 오류: {e}")
        # 실패 시 기본 인코딩으로 재시도
        df.to_csv(locations_file, index=False, encoding='utf-8')

def save_optimization_result_to_csv(result, vehicle_count, vehicle_capacity, project_id: str | None = None):
    """최적화 결과를 CSV 파일로 저장합니다."""
    pid = project_id or get_project_id()
    # 요약 정보
    summary_data = {
        'Total_Distance_m': [result['total_distance']],
        'Total_Time_s': [result.get('total_time', 0)],
        'Total_Load': [result['total_load']],
        'Objective_Value': [result['objective']],
        'Vehicle_Count': [vehicle_count],
        'Vehicle_Capacity': [vehicle_capacity]
    }
    
    # 요약 정보 CSV 저장 (UTF-8 BOM으로 Excel 호환성 확보)
    summary_df = pd.DataFrame(summary_data)
    try:
        summary_df.to_csv(project_path('optimization_summary.csv', pid), index=False, encoding='utf-8-sig')
        print("요약 파일을 UTF-8-SIG 인코딩으로 저장했습니다.")
    except Exception as e:
        print(f"요약 파일 저장 중 오류: {e}")
        summary_df.to_csv(project_path('optimization_summary.csv', pid), index=False, encoding='utf-8')
    
    # 상세 경로 정보 CSV 저장 (UTF-8 BOM으로 Excel 호환성 확보)
    route_details = []
    # per-route 이전 누적값을 추적하여 정류장별 Load(수요)를 계산
    # load locations map for id lookup
    try:
        loc_df_for_ids = pd.read_csv(project_path('locations.csv', pid), encoding='utf-8-sig')
    except Exception:
        try:
            loc_df_for_ids = pd.read_csv(project_path('locations.csv', pid), encoding='utf-8')
        except Exception:
            loc_df_for_ids = pd.DataFrame()

    def _normalize_name_for_lookup(s: str | None) -> str:
        if s is None:
            return ''
        try:
            return ' '.join(str(s).strip().lower().split())
        except Exception:
            return str(s).strip().lower()

    name_to_id = {}
    if not loc_df_for_ids.empty and 'name' in loc_df_for_ids.columns and 'id' in loc_df_for_ids.columns:
        for _, lr in loc_df_for_ids.iterrows():
            try:
                name_to_id[_normalize_name_for_lookup(lr['name'])] = str(lr['id'])
            except Exception:
                continue

    for route in result['routes']:
        prev_cum = 0
        for i, waypoint in enumerate(route['waypoints']):
            cumulative = int(waypoint.get('load', 0) or 0)
            # depot은 수요 0, 그 외는 (현재 누적 - 이전 누적)
            load_delta = 0 if str(waypoint.get('type')) == 'depot' else max(0, cumulative - prev_cum)
            prev_cum = cumulative
            route_details.append({
                'Vehicle_ID': route['vehicle_id'] + 1,
                'Route_Distance_m': waypoint.get('cumulative_distance', 0),
                'Route_Time_s': waypoint.get('cumulative_time', 0),
                'Route_Load': route['load'],
                'Stop_Order': i + 1,
                'Location_Name': waypoint['name'],
                'Location_ID': name_to_id.get(_normalize_name_for_lookup(waypoint.get('name')), ''),
                'Location_Type': waypoint['type'],
                'Load': load_delta,
                'Cumulative_Load': cumulative
            })
    
    routes_df = pd.DataFrame(route_details)
    try:
        routes_df.to_csv(project_path('optimization_routes.csv', pid), index=False, encoding='utf-8-sig')
        print("상세 경로 파일을 UTF-8-SIG 인코딩으로 저장했습니다.")
    except Exception as e:
        print(f"상세 경로 파일 저장 중 오류: {e}")
        routes_df.to_csv(project_path('optimization_routes.csv', pid), index=False, encoding='utf-8')
    
    print(f"최적화 결과가 저장되었습니다:")
    print(f"- 요약: {project_path('optimization_summary.csv', pid)}")
    print(f"- 상세 경로: {project_path('optimization_routes.csv', pid)}")

@app.route('/')
def index():
    """메인 페이지를 렌더링합니다."""
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN')
    return render_template('index.html', mapbox_token=mapbox_token)

@app.route('/api/locations', methods=['GET'])
def get_locations():
    """모든 위치 데이터를 JSON 형식으로 반환합니다."""
    pid = get_project_id()
    df = load_data(pid)
    # 결측치(NaN)를 None으로 변환하고 그대로의 순서를 유지합니다.
    records = df.where(pd.notnull(df), None).to_dict(orient='records')
    return jsonify(records)

@app.route('/api/locations', methods=['POST'])
def add_location():
    """새로운 위치를 추가합니다."""
    try:
        data = request.json
        pid = get_project_id()
        df = load_data(pid)
        # 안전한 6자리 영숫자 ID 생성(충돌 체크 포함)
        existing_ids = set(df['id'].astype(str).tolist()) if not df.empty and 'id' in df.columns else set()
        # 만약 테이블이 비어있다면 Depot(초기 생성)이 이미 존재하거나, 새 프로젝트일 수 있음.
        # 요청으로 특정 id가 제공된 경우(드문 케이스) 우선 사용 가능하도록 처리
        if data and data.get('id'):
            candidate = str(data.get('id'))
            if candidate in existing_ids:
                return jsonify({'error': 'ID already exists'}), 409
            new_id = candidate
        else:
            # 충돌이 거의 발생하지 않으므로 간단한 재시도로 충분
            attempts = 0
            new_id = None
            while attempts < 10:
                # 기본적으로 4자리(대문자+숫자) ID를 생성합니다.
                candidate = generate_short_id(4)
                if candidate not in existing_ids:
                    new_id = candidate
                    break
                attempts += 1
            if new_id is None:
                # 드물게 모든 시도가 실패하면 UUIDfallback
                import uuid
                new_id = uuid.uuid4().hex[:8]

        new_location = {
            'id': str(new_id),
            'name': str(data['name']),
            'lon': float(data['lon']),
            'lat': float(data['lat']),
            'demand': int(data['demand']) if data.get('demand') else 0
        }

        df = pd.concat([df, pd.DataFrame([new_location])], ignore_index=True)
        save_data(df, pid)
        return jsonify(new_location), 201
    except Exception as e:
        print(f"Error in add_location: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/locations/<location_id>', methods=['PUT'])
def update_location(location_id):
    """기존 위치 정보를 수정합니다."""
    try:
        data = request.json
        pid = get_project_id()
        df = load_data(pid)
        
        # IDs are stored as strings; ensure comparison as string
        str_id = str(location_id)
        if str_id in df['id'].values:
            idx = df[df['id'] == str_id].index[0]
            # 이름 제공 시에만 갱신
            if 'name' in data and data.get('name') is not None:
                df.loc[idx, 'name'] = str(data.get('name', df.loc[idx, 'name']))
            
            # Check if this is the first location (depot) - force demand to 0
            # Depot 결정: 파일상 첫 번째 행(파일 생성 시 Depot을 제일 처음에 둡니다)
            try:
                first_id = df.iloc[0]['id']
            except Exception:
                first_id = df['id'].min() if 'id' in df.columns else None
            is_depot = df.loc[idx, 'id'] == first_id
            if is_depot:
                df.loc[idx, 'demand'] = 0
            else:
                if 'demand' in data and data.get('demand') is not None:
                    df.loc[idx, 'demand'] = int(data.get('demand', df.loc[idx, 'demand']))

            # 위경도 전달 시 갱신(드래그 앤 드롭 반영)
            if 'lon' in data and data.get('lon') is not None:
                try:
                    df.loc[idx, 'lon'] = float(data.get('lon'))
                except (ValueError, TypeError):
                    pass
            if 'lat' in data and data.get('lat') is not None:
                try:
                    df.loc[idx, 'lat'] = float(data.get('lat'))
                except (ValueError, TypeError):
                    pass
            
            save_data(df, pid)

            # 위치 변경에 따른 캐시/결과 파일 무효화 처리
            try:
                cache_files = [
                    project_path('time_matrix.csv', pid),
                    project_path('distance_matrix.csv', pid),
                    project_path('optimization_routes.csv', pid),
                    project_path('optimization_summary.csv', pid),
                    project_path('generated_routes.json', pid),
                    project_path('route_metadata.json', pid)
                ]
                for f in cache_files:
                    if os.path.exists(f):
                        os.remove(f)
                        print(f"⚠️ 위치 변경으로 캐시/결과 파일 삭제: {f}")
            except Exception as ce:
                print(f"캐시 파일 삭제 실패(update_location): {ce}")

            return jsonify(df.loc[idx].to_dict())
        return jsonify({'error': 'Location not found'}), 404
    except Exception as e:
        print(f"Error in update_location: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/locations/<location_id>', methods=['DELETE'])
def delete_location(location_id):
    """위치를 삭제합니다."""
    pid = get_project_id()
    df = load_data(pid)
    str_id = str(location_id)
    if str_id in df['id'].values:
        df = df[df['id'] != str_id]
        save_data(df, pid)
        return '', 204
    return jsonify({'error': 'Location not found'}), 404


@app.route('/api/optimize-settings', methods=['GET'])
def get_optimize_settings():
    """프로젝트별 최적화 팝업 설정을 반환합니다. 설정 파일이 없으면 exists=False를 반환합니다."""
    try:
        pid = get_project_id()
        settings_path = project_path('optimization_settings.json', pid)
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                return jsonify({'exists': True, 'settings': data})
            except Exception as e:
                return jsonify({'error': f'Failed to load settings: {e}'}), 500
        return jsonify({'exists': False, 'settings': {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/optimize-settings', methods=['POST'])
def save_optimize_settings():
    """요청 바디(JSON)를 받아 프로젝트 폴더에 optimization_settings.json으로 저장합니다."""
    try:
        pid = get_project_id()
        payload = request.get_json(silent=True) or {}
        settings_path = project_path('optimization_settings.json', pid)
        # 저장: UTF-8로 human-readable하게
        with open(settings_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return jsonify({'saved': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download_file():
    """CSV 파일을 다운로드합니다. UTF-8 BOM으로 인코딩하여 Excel에서도 한글이 정상 표시됩니다."""
    pid = get_project_id()
    df = load_data(pid)
    
    # UTF-8 BOM으로 인코딩된 CSV 생성
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    # UTF-8 BOM 추가 (Excel 호환성)
    csv_content = '\ufeff' + output.getvalue()
    
    response = make_response(csv_content.encode('utf-8-sig'))
    response.headers["Content-Disposition"] = "attachment; filename=locations.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return response

@app.route('/download-demand-form')
def download_demand_form():
    """apps 폴더에 있는 demand_form.csv를 다운로드합니다."""
    try:
        # 앱 루트 기준 파일 제공
        directory = os.path.abspath(os.path.dirname(__file__))
        return send_from_directory(directory, 'demand_form.csv', as_attachment=True, download_name='demand_form.csv')
    except Exception as e:
        return jsonify({ 'error': f'Failed to download form: {str(e)}' }), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """CSV 파일을 업로드합니다."""
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file and file.filename.endswith('.csv'):
        pid = get_project_id()
        # 업로드된 파일의 인코딩을 자동 감지하여 읽기
        encodings_to_try = ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949']
        df = None
        
        for encoding in encodings_to_try:
            try:
                # 파일 포인터를 처음으로 되돌리기
                file.seek(0)
                df = pd.read_csv(file, encoding=encoding)
                print(f"업로드 파일을 {encoding} 인코딩으로 읽었습니다.")
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"파일 읽기 오류 ({encoding}): {e}")
                continue
        
        if df is None:
            return 'File encoding not supported. Please use UTF-8, EUC-KR, or CP949 encoding.', 400
            
        # 컬럼 정규화: 공백 제거 및 소문자 변환, 일부 동의어 매핑
        try:
            original_cols = list(df.columns)
            # 칼럼명에서 BOM 또는 보이지 않는 특수문자 제거 후 소문자화
            def clean_col(c):
                s = str(c)
                s = s.replace('\ufeff', '')  # UTF-8 BOM 제거
                s = s.replace('\u200b', '')  # zero-width space 제거
                return s.strip().lower()

            normalized = {col: clean_col(col) for col in df.columns}
            df.rename(columns=normalized, inplace=True)
            # 동의어 처리
            synonym_map = {}
            if 'longitude' in df.columns and 'lon' not in df.columns:
                synonym_map['longitude'] = 'lon'
            if 'latitude' in df.columns and 'lat' not in df.columns:
                synonym_map['latitude'] = 'lat'
            if 'x' in df.columns and 'lon' not in df.columns:
                synonym_map['x'] = 'lon'
            if 'y' in df.columns and 'lat' not in df.columns:
                synonym_map['y'] = 'lat'
            if synonym_map:
                df.rename(columns=synonym_map, inplace=True)

            required_cols = ['id', 'name', 'lon', 'lat', 'demand']
            if not all(col in df.columns for col in required_cols):
                return 'Invalid CSV format. Required columns: id, name, lon, lat, demand', 400

            # 타입 보정(가능할 때만)
            # lon/lat은 숫자여야 하며 유효한 범위인지 검사
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['demand'] = pd.to_numeric(df['demand'], errors='coerce').fillna(0)

            # 기본적인 결측/타입 검사: 필수 좌표가 없는 행은 오류로 처리
            bad_coord = df[df['lon'].isna() | df['lat'].isna()]
            if not bad_coord.empty:
                rows = bad_coord.index.tolist()
                return f'Invalid coordinates in rows: {rows}', 400

            # 좌표 범위 체크
            invalid_bounds = df[(df['lon'] < -180) | (df['lon'] > 180) | (df['lat'] < -90) | (df['lat'] > 90)]
            if not invalid_bounds.empty:
                return f'Latitude/longitude out of range for rows: {invalid_bounds.index.tolist()}', 400

            # demand는 음수일 수 없음
            if (df['demand'] < 0).any():
                return f'Demand must be non-negative for all rows', 400

            # id는 문자열로 정규화 (빈값은 빈 문자열)
            df['id'] = df['id'].fillna('').astype(str).str.strip()

            # 빈 id에 대해서는 4자리 대문자+숫자 ID를 생성
            existing_ids = set(df['id'][df['id'] != ''].tolist())
            new_ids = []
            for idx, val in df['id'].items():
                if not val:
                    # 생성 시 충돌이 없을 때까지 재시도
                    attempts = 0
                    candidate = None
                    while attempts < 20:
                        candidate = generate_short_id(4)
                        if candidate not in existing_ids:
                            existing_ids.add(candidate)
                            break
                        attempts += 1
                    if candidate is None:
                        import uuid
                        candidate = uuid.uuid4().hex[:4].upper()
                    df.at[idx, 'id'] = candidate
                    new_ids.append((idx, candidate))

            # 중복 ID 검사
            dupes = df[df['id'].duplicated(keep=False)]['id'].unique().tolist()
            if dupes:
                # 사용자가 이해하기 쉬운 한국어 메시지 반환
                return f'업로드 실패: CSV에 중복된 ID가 존재합니다. 중복 ID: {dupes}', 400

            # depot 보장: id '1'이 없다면 첫 행을 depot으로 설정
            if '1' not in df['id'].values:
                # first row를 depot으로 설정
                df.iloc[0, df.columns.get_loc('id')] = '1'
                df.iloc[0, df.columns.get_loc('demand')] = 0

            # 모든 id를 문자열로 유지
            df['id'] = df['id'].astype(str)

            # demand를 정수로
            df['demand'] = df['demand'].astype(int)

        except Exception as norm_e:
            print(f"업로드 데이터 정규화 오류: {norm_e}")
            return f'Failed to normalize uploaded CSV: {norm_e}', 400

        # 저장
        save_data(df, pid)

        # 업로드로 인해 이전 계산/캐시 파일 무효화(데이터 일관성)
        cache_files = [
            project_path('time_matrix.csv', pid),
            project_path('distance_matrix.csv', pid),
            project_path('optimization_routes.csv', pid),
            project_path('optimization_summary.csv', pid),
            project_path('generated_routes.json', pid),
            project_path('route_metadata.json', pid)
        ]
        cleared = []
        for f in cache_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    cleared.append(f)
                    print(f"⚠️ 업로드로 인해 캐시/결과 파일 삭제: {f}")
            except Exception as ce:
                print(f"캐시 파일 삭제 실패: {f} - {ce}")

        # 단순 텍스트 응답 유지(프론트 기존 로직 호환)
        return 'File uploaded successfully', 200
    return 'Invalid file type', 400

@app.route('/api/create-matrix', methods=['POST'])
def create_matrix():
    """매트릭스를 생성합니다."""
    try:
        data = request.json
        transport_mode = data.get('transportMode', 'car')
        metric = data.get('metric', 'Recommendation')
        pid = get_project_id()
        
        # 매트릭스 생성
        result = create_matrix_from_locations(
            transport_mode,
            metric,
            locations_file=project_path('locations.csv', pid),
            time_filename=project_path('time_matrix.csv', pid),
            distance_filename=project_path('distance_matrix.csv', pid)
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'time_matrix': result.get('time_matrix'),
                'distance_matrix': result.get('distance_matrix'),
                'locations': result['locations']
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'매트릭스 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/check-matrix-file', methods=['GET'])
def check_matrix_file():
    """시간 및 거리 매트릭스 파일 존재 여부를 확인합니다."""
    pid = get_project_id()
    time_matrix_file = project_path('time_matrix.csv', pid)
    distance_matrix_file = project_path('distance_matrix.csv', pid)
    
    # 두 파일 모두 존재해야 함
    exists = os.path.exists(time_matrix_file) and os.path.exists(distance_matrix_file)
    
    return jsonify({
        'exists': exists,
        'time_matrix_exists': os.path.exists(time_matrix_file),
        'distance_matrix_exists': os.path.exists(distance_matrix_file)
    })

@app.route('/api/optimize', methods=['POST'])
def optimize():
    """최적화를 실행합니다."""
    try:
        from utils.vrp_solver import solve_vrp
        pid = get_project_id()
        
        # 🗑️ 기존 경로 캐시 파일 삭제 (새로운 최적화 시작)
        route_cache_files = [project_path('generated_routes.json', pid), project_path('route_metadata.json', pid)]
        for cache_file in route_cache_files:
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    print(f"✅ 기존 경로 캐시 삭제: {cache_file}")
                except Exception as e:
                    print(f"⚠️ 캐시 파일 삭제 실패: {cache_file} - {e}")
        
        data = request.json
        vehicle_count = data.get('vehicleCount', 1)
        vehicle_capacity = data.get('vehicleCapacity', 10)
        time_limit_sec = data.get('timeLimitSec', 60)
        
        # 목적함수 설정 추출 (기본값 설정)
        primary_objective = data.get('primaryObjective', 'distance')
        tiebreaker1 = data.get('tiebreaker1', 'none')
        tiebreaker2 = data.get('tiebreaker2', 'none')
        additional_objectives = data.get('additionalObjectives', [])
        
        # 매트릭스 파일 존재 여부 확인
        time_matrix_file = project_path('time_matrix.csv', pid)
        distance_matrix_file = project_path('distance_matrix.csv', pid)
        
        if not os.path.exists(time_matrix_file):
            return jsonify({
                'success': False,
                'message': 'Time matrix file not found. Please create matrix first.'
            }), 400
            
        if not os.path.exists(distance_matrix_file):
            return jsonify({
                'success': False,
                'message': 'Distance matrix file not found. Please create matrix first.'
            }), 400
        
        # locations.csv 파일이 존재하는지 확인
        locations_file = project_path('locations.csv', pid)
        if not os.path.exists(locations_file):
            return jsonify({
                'success': False,
                'message': 'Locations file not found. Please add locations first.'
            }), 400
        
        # 시작/종료 옵션 (자유 출발, depot 도착 고정) - 선택적
        # 라디오: routeMode = FREE_START_DEPOT_END | DEPOT_START_OPEN_END
        route_mode = data.get('routeMode', 'FREE_START_DEPOT_END')
        # 구버전 체크박스 호환 처리 (있다면 우선)
        start_anywhere = bool(data.get('startAnywhere', False))
        end_at_depot_only = bool(data.get('endAtDepotOnly', False))
        open_end = False
        if 'routeMode' in data or (not start_anywhere and not end_at_depot_only):
            # routeMode를 solver 플래그로 매핑
            if route_mode == 'FREE_START_DEPOT_END':
                start_anywhere = True
                end_at_depot_only = True
            elif route_mode == 'DEPOT_START_OPEN_END':
                start_anywhere = False
                end_at_depot_only = False
                open_end = True

        # VRP 최적화 실행 (새로운 매개변수 사용)
        result = solve_vrp(
            locations_csv_path=locations_file,
            time_matrix_path=time_matrix_file,
            distance_matrix_path=distance_matrix_file,
            vehicle_capacity=vehicle_capacity,
            num_vehicles=vehicle_count,
            time_limit_sec=time_limit_sec,
            primary_objective=primary_objective,
            tiebreaker1=tiebreaker1,
            tiebreaker2=tiebreaker2,
            additional_objectives=additional_objectives,
            start_anywhere=start_anywhere,
            end_at_depot_only=end_at_depot_only,
            open_end=open_end
        )
        
        if result['success']:
            # CSV 파일로 최적화 결과 저장
            save_optimization_result_to_csv(result, vehicle_count, vehicle_capacity, pid)
            
            return jsonify({
                'success': True,
                'message': 'Optimization completed successfully',
                'vehicleCount': vehicle_count,
                'vehicleCapacity': vehicle_capacity,
                'routes': result['routes'],
                'objective': result['objective'],
                'total_distance': result['total_distance'],
                'total_time': result.get('total_time', 0),
                'total_load': result['total_load']
            })
        else:
            # 상세한 오류 정보 제공
            error_message = result.get('error', 'Optimization failed')
            
            # 검증 오류인 경우 더 구체적인 메시지
            if 'validation_errors' in result:
                error_message = "입력 데이터 오류:\n" + "\n".join([f"• {error}" for error in result['validation_errors']])
            
            # 진단 정보가 있는 경우 추가
            if 'diagnosis' in result:
                diagnosis = result['diagnosis']
                if diagnosis['type'] == 'capacity_constraint':
                    error_message = f"용량 부족 오류: 총 수요가 총 차량 용량을 초과합니다.\n해결방법: 차량 수를 늘리거나 용량을 증가시켜주세요."
                elif diagnosis['type'] == 'individual_capacity':
                    error_message = f"개별 용량 초과: 일부 위치의 수요가 차량 용량을 초과합니다.\n해결방법: 차량 용량을 늘려주세요."
                else:
                    error_message = diagnosis['message']
            
            return jsonify({
                'success': False,
                'message': error_message
            }), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'최적화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/check-routes', methods=['GET'])
def check_routes():
    """optimization_routes.csv와 locations.csv 파일의 존재를 확인합니다."""
    pid = get_project_id()
    routes_file = project_path('optimization_routes.csv', pid)
    locations_file = project_path('locations.csv', pid)
    
    try:
        # Routes 파일 존재 확인
        if not os.path.exists(routes_file):
            return jsonify({
                'has_routes': False,
                'message': 'Routes file not found'
            })
        
        # Routes 파일이 비어있지 않은지 확인
        if os.path.getsize(routes_file) <= 1:  # 1바이트 이하면 빈 파일
            return jsonify({
                'has_routes': False,
                'message': 'Routes file is empty'
            })
            
        # Locations 파일 존재 확인
        if not os.path.exists(locations_file):
            return jsonify({
                'has_routes': False,
                'message': 'Locations file not found'
            })
            
        # Locations 파일이 비어있지 않은지 확인
        if os.path.getsize(locations_file) <= 1:
            return jsonify({
                'has_routes': False,
                'message': 'Locations file is empty'
            })
        
        # 모든 파일이 존재하고 비어있지 않으면 OK
        return jsonify({
            'has_routes': True,
            'message': 'Both routes and locations files exist'
        })
            
    except Exception as e:
        return jsonify({
            'has_routes': False,
            'message': f'Error checking routes: {str(e)}'
        })

# Route Visualization 관련 라우트들
from datetime import datetime
from utils.tmap_route import TmapRoute

@app.route('/route-visualization')
def route_visualization():
    """독립적인 route visualization 페이지"""
    pid = get_project_id()
    # 기존 최적화 결과가 있으면 로드
    route_data = {
        'routes': [],
        'total_distance': 'N/A',
        'total_duration': 'N/A', 
        'route_count': 0,
        'optimization_score': 'N/A'
    }
    
    # optimization_routes.csv 파일이 있으면 데이터 로드
    try:
        if os.path.exists(project_path('optimization_routes.csv', pid)):
            routes_df = pd.read_csv(project_path('optimization_routes.csv', pid), encoding='utf-8-sig')
            route_data = convert_routes_df_to_visualization_data(routes_df, pid)
    except Exception as e:
        print(f"Route data loading error: {e}")
    
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN')
    return render_template('route_visualization.html', 
                         route_data=route_data, 
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                         mapbox_token=mapbox_token)

@app.route('/generate-route-html', methods=['POST'])
def generate_route_html():
    """라우트 데이터를 받아서 완전한 HTML 파일을 생성"""
    try:
        pid = get_project_id()
        request_data = request.get_json()
        
        # 현재 최적화 결과 로드
        route_data = {
            'routes': [],
            'total_distance': 'N/A',
            'total_duration': 'N/A',
            'route_count': 0,
            'optimization_score': 'N/A'
        }
        
        if os.path.exists(project_path('optimization_routes.csv', pid)):
            routes_df = pd.read_csv(project_path('optimization_routes.csv', pid), encoding='utf-8-sig')
            route_data = convert_routes_df_to_visualization_data(routes_df, pid)
        
        # Per-project report path
        report_filename = 'route_report.html'
        report_path = project_path(report_filename, pid)

        # If report exists, serve it directly from project folder
        if os.path.exists(report_path):
            proj_dir = os.path.dirname(report_path)
            return send_from_directory(proj_dir, report_filename, mimetype='text/html')

        # Generate standalone HTML and save it into project folder
        html_content = generate_standalone_route_html(route_data)
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f"Failed to write report for project {pid}: {e}")

        proj_dir = os.path.dirname(report_path)
        return send_from_directory(proj_dir, report_filename, mimetype='text/html')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate-route-table-report', methods=['POST'])
def generate_route_table_report():
    """Generate the table-based route report (reads generated_routes.json per project) and return HTML."""
    try:
        pid = get_project_id()
        report_filename = 'route_table_report.html'
        report_path = project_path(report_filename, pid)

        # If a per-project report already exists, serve it directly (reuse)
        if os.path.exists(report_path):
            proj_dir = os.path.dirname(report_path)
            return send_from_directory(proj_dir, report_filename, mimetype='text/html')

        # Otherwise generate and save it
        try:
            from utils.report_generator import generate_route_table_report_html
            report_html = generate_route_table_report_html(project_id=pid)
        except Exception as e:
            print(f"Failed to generate table report for project {pid}: {e}")
            return jsonify({'error': str(e)}), 500

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_html)
        except Exception as e:
            print(f"Warning: could not write report file {report_path}: {e}")

        proj_dir = os.path.dirname(report_path)
        return send_from_directory(proj_dir, report_filename, mimetype='text/html')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def convert_routes_df_to_visualization_data(routes_df, pid: str | None = None):
    """최적화 결과 DataFrame을 visualization용 데이터로 변환"""
    route_data = {
        'routes': [],
        'total_distance': 'N/A',
        'total_duration': 'N/A',
        'route_count': 0,
        'optimization_score': 'N/A'
    }
    
    try:
        # 라우트 개수 계산
        if 'Vehicle' in routes_df.columns:
            unique_vehicles = routes_df['Vehicle'].unique()
            route_data['route_count'] = len(unique_vehicles)
            
            # 각 차량별 라우트 정보 구성
            for vehicle_id in unique_vehicles:
                vehicle_routes = routes_df[routes_df['Vehicle'] == vehicle_id]
                
                route_info = {
                    'vehicle_id': int(vehicle_id),
                    'stops': [],
                    'geometry': None
                }
                
                # 정류장 정보 추가
                for _, row in vehicle_routes.iterrows():
                    stop = {
                        'name': row.get('Location', f'Stop {len(route_info["stops"]) + 1}'),
                        'latitude': float(row.get('Lat', 0)),
                        'longitude': float(row.get('Lon', 0)),
                        'order': int(row.get('Order', len(route_info['stops'])))
                    }
                    route_info['stops'].append(stop)
                
                route_data['routes'].append(route_info)
        
        # 통계 정보 계산 (요약 파일이 있으면)
        if pid is None:
            pid = 'default'
        summary_file = project_path('optimization_summary.csv', pid)
        if os.path.exists(summary_file):
            summary_df = pd.read_csv(summary_file, encoding='utf-8-sig')
            if not summary_df.empty:
                total_dist = summary_df.get('Total_Distance_m', [0]).iloc[0]
                route_data['total_distance'] = f"{total_dist/1000:.1f} km" if total_dist > 0 else 'N/A'
                
                total_time = summary_df.get('Total_Time_s', [0]).iloc[0]
                route_data['total_duration'] = f"{total_time//60:.0f} min" if total_time > 0 else 'N/A'
                
                # 간단한 최적화 점수 계산 (실제로는 더 복잡한 로직 필요)
                if total_dist > 0 and route_data['route_count'] > 0:
                    avg_dist_per_route = total_dist / route_data['route_count'] / 1000
                    score = max(0, 100 - avg_dist_per_route * 2)  # 임시 계산식
                    route_data['optimization_score'] = f"{score:.0f}%"
                    
    except Exception as e:
        print(f"Error converting route data: {e}")
    
    return route_data



@app.route('/get-routes', methods=['GET'])
def get_routes():
    """스마트 경로 로딩: 캐시된 데이터가 있으면 바로 반환, 없으면 생성"""
    try:
        pid = get_project_id()
        # 1️⃣ 캐시된 경로 파일 확인
        if os.path.exists(project_path('generated_routes.json', pid)):
            print("📂 캐시된 경로 데이터 발견, 로딩 중...")
            
            try:
                with open(project_path('generated_routes.json', pid), 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                # 캐시된 vehicle_routes에 route_load나 waypoint.demand가 없을 수 있으므로 보강
                vehicle_routes = cached_data.get('vehicle_routes', {})
                try:
                    if os.path.exists(project_path('optimization_routes.csv', pid)):
                        routes_df = pd.read_csv(project_path('optimization_routes.csv', pid), encoding='utf-8-sig')
                        routes_df['Vehicle_ID'] = pd.to_numeric(routes_df['Vehicle_ID'], errors='coerce')
                        routes_df['Stop_Order'] = pd.to_numeric(routes_df['Stop_Order'], errors='coerce')
                        routes_df = routes_df.dropna(subset=['Vehicle_ID', 'Stop_Order'])
                        # Load 컬럼 보장
                        if 'Load' not in routes_df.columns and 'Cumulative_Load' in routes_df.columns:
                            try:
                                routes_df['Cumulative_Load'] = pd.to_numeric(routes_df['Cumulative_Load'], errors='coerce').fillna(0).astype(int)
                                routes_df['Load'] = 0
                                for vid, grp in routes_df.groupby('Vehicle_ID'):
                                    grp_sorted = grp.sort_values('Stop_Order').copy()
                                    prev = 0
                                    loads = []
                                    for _, r in grp_sorted.iterrows():
                                        loc_type = str(r.get('Location_Type', ''))
                                        cum = int(r.get('Cumulative_Load', 0) or 0)
                                        delta = 0 if loc_type == 'depot' else max(0, cum - prev)
                                        loads.append(delta)
                                        prev = cum
                                    routes_df.loc[grp_sorted.index, 'Load'] = loads
                            except Exception as _e:
                                print(f"Load 보강 실패(get_routes): {_e}")
                        # 차량별 최종 Cumulative_Load 사전 생성
                        final_load_by_vehicle = {}
                        for vid, grp in routes_df.groupby('Vehicle_ID'):
                            grp_sorted = grp.sort_values('Stop_Order')
                            try:
                                final_val = int(pd.to_numeric(grp_sorted['Cumulative_Load'], errors='coerce').dropna().iloc[-1])
                            except Exception:
                                final_val = 0
                            final_load_by_vehicle[int(vid)] = final_val
                        # 캐시 데이터 보강: route_load, waypoint.demand
                        def _normalize_name_local(s: str | None) -> str:
                            if s is None:
                                return ''
                            try:
                                return ' '.join(str(s).strip().lower().split())
                            except Exception:
                                return str(s).strip().lower()

                        for key, route in vehicle_routes.items():
                            vid = int(route.get('vehicle_id', key))
                            if 'route_load' not in route or route.get('route_load') in (None, 0):
                                route['route_load'] = final_load_by_vehicle.get(vid, 0)
                            # waypoint.demand 주입 (ID 우선, 이름 폴백)
                            try:
                                grp = routes_df[routes_df['Vehicle_ID'] == vid].sort_values('Stop_Order').copy()
                                if 'waypoints' in route and isinstance(route['waypoints'], list):
                                    for idx, wp in enumerate(route['waypoints']):
                                        wp_name = str(wp.get('name', ''))
                                        wp_id = str(wp.get('id', '')) if wp.get('id') is not None else None
                                        wp_name_norm = _normalize_name_local(wp_name)
                                        load_val = 0
                                        # 1) Location_ID 컬럼이 있으면 ID로 우선 매칭
                                        if 'Location_ID' in grp.columns and wp_id:
                                            matched = grp[grp['Location_ID'].astype(str) == wp_id]
                                            if not matched.empty:
                                                try:
                                                    load_val = int(matched.iloc[0].get('Load', 0) or 0)
                                                    wp['demand'] = load_val
                                                    continue
                                                except Exception:
                                                    load_val = 0
                                        # 2) 동일한 순서의 후보 사용(인덱스 기반)
                                        candidate = grp.iloc[idx] if idx < len(grp) else None
                                        if candidate is not None:
                                            # ID가 있으면 비교
                                            if 'Location_ID' in candidate and pd.notna(candidate.get('Location_ID')) and wp_id:
                                                if str(candidate.get('Location_ID')) == wp_id:
                                                    load_val = int(candidate.get('Load', 0) or 0)
                                                    wp['demand'] = load_val
                                                    continue
                                            # 이름으로 비교 (정규화)
                                            cand_name_norm = _normalize_name_local(candidate.get('Location_Name', ''))
                                            if cand_name_norm and cand_name_norm == wp_name_norm:
                                                load_val = int(candidate.get('Load', 0) or 0)
                                                wp['demand'] = load_val
                                                continue
                                        # 3) 이름으로 전체 검색 폴백
                                        if 'Location_Name' in grp.columns:
                                            # normalized match across the group
                                            try:
                                                matched = grp[grp['Location_Name'].astype(str).apply(lambda x: _normalize_name_local(x) == wp_name_norm)]
                                            except Exception:
                                                matched = grp[grp['Location_Name'].astype(str) == wp_name]
                                            if not matched.empty:
                                                try:
                                                    load_val = int(matched.iloc[0].get('Load', 0) or 0)
                                                except Exception:
                                                    load_val = 0
                                        wp['demand'] = load_val
                            except Exception as _wp_e:
                                print(f"waypoint.demand 보강 실패(V{vid}): {_wp_e}")
                except Exception as enrich_error:
                    print(f"⚠️ 캐시 보강 중 오류(Load): {enrich_error}")

                print(f"✅ 캐시된 경로 로드 성공: {len(cached_data.get('vehicle_routes', {}))}개 차량")
                
                return jsonify({
                    'success': True,
                    'from_cache': True,
                    'generated_at': cached_data.get('generated_at'),
                    'vehicle_routes': vehicle_routes,
                    'statistics': cached_data.get('statistics', {})
                })
                
            except Exception as cache_error:
                print(f"⚠️ 캐시 로드 실패: {cache_error}, T-map으로 새로 생성합니다.")
                # 캐시 로드 실패 시 아래로 계속 진행해서 새로 생성
        
        # 2️⃣ 캐시가 없으면 T-map API로 새로 생성
        print("🚀 캐시된 데이터가 없어서 T-map API로 새로 생성합니다...")
        return generate_routes_from_csv_internal()
        
    except Exception as e:
        print(f"❌ 경로 로딩 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate-routes-from-csv', methods=['POST'])
def generate_routes_from_csv():
    """강제로 T-map API를 호출해서 새로운 경로 생성 (Refresh Routes용)
    선택적 옵션(searchOption, carType, viaTime, startTime)을 JSON 바디로 받아 전달한다.
    모두 문자열로 처리.
    """
    try:
        options = request.get_json(silent=True) or {}
    except Exception:
        options = {}
    return generate_routes_from_csv_internal(options)

def generate_routes_from_csv_internal(options: dict | None = None):
    """optimization_routes.csv 파일을 읽어서 T-map으로 실제 경로 생성"""
    try:
        pid = get_project_id()
        options = options or {}
        # 문자열로 보장
        opt_search = options.get('searchOption')
        opt_car = options.get('carType')
        opt_via = options.get('viaTime')
        opt_start = options.get('startTime')
        if opt_search is not None:
            opt_search = str(opt_search)
        if opt_car is not None:
            opt_car = str(opt_car)
        if opt_via is not None:
            opt_via = str(opt_via)
        if opt_start is not None:
            opt_start = str(opt_start)
        
        print("🚀 경로 생성 시작...")
        
        # CSV 파일들 읽기
        if not os.path.exists(project_path('optimization_routes.csv', pid)):
            return jsonify({'error': 'optimization_routes.csv 파일이 없습니다.'}), 400
        
        if not os.path.exists(project_path('locations.csv', pid)):
            return jsonify({'error': 'locations.csv 파일이 없습니다.'}), 400
            
        print("📁 CSV 파일 읽기 중...")

        routes_df = pd.read_csv(project_path('optimization_routes.csv', pid), encoding='utf-8-sig')
        locations_df = pd.read_csv(project_path('locations.csv', pid), encoding='utf-8-sig')
        
        # 데이터 타입 강제 변환
        routes_df['Vehicle_ID'] = pd.to_numeric(routes_df['Vehicle_ID'], errors='coerce')
        routes_df['Stop_Order'] = pd.to_numeric(routes_df['Stop_Order'], errors='coerce')
        # Load 컬럼이 없을 경우 Cumulative_Load 차분으로 생성 (depot=0)
        if 'Load' not in routes_df.columns:
            try:
                routes_df['Cumulative_Load'] = pd.to_numeric(routes_df['Cumulative_Load'], errors='coerce').fillna(0).astype(int)
                routes_df['Load'] = 0
                for vid, grp in routes_df.groupby('Vehicle_ID'):
                    grp_sorted = grp.sort_values('Stop_Order').copy()
                    prev = 0
                    loads = []
                    for _, r in grp_sorted.iterrows():
                        loc_type = str(r.get('Location_Type', ''))
                        cum = int(r.get('Cumulative_Load', 0) or 0)
                        delta = 0 if loc_type == 'depot' else max(0, cum - prev)
                        loads.append(delta)
                        prev = cum
                    routes_df.loc[grp_sorted.index, 'Load'] = loads
            except Exception as _e:
                print(f"Load 컬럼 생성 실패: {_e}")
        locations_df['lon'] = pd.to_numeric(locations_df['lon'], errors='coerce')
        locations_df['lat'] = pd.to_numeric(locations_df['lat'], errors='coerce')
        
        # NaN 값 제거
        routes_df = routes_df.dropna(subset=['Vehicle_ID', 'Stop_Order'])
        locations_df = locations_df.dropna(subset=['lon', 'lat'])
        
        print(f"📊 Routes 데이터: {len(routes_df)}행, Locations 데이터: {len(locations_df)}행")
        
        # 위치 정보를 딕셔너리로 변환 (ID 우선 조회, name 폴백)
        # location_by_id: id -> location dict
        # location_by_name: name -> location dict (폴백용, 중복 시 첫 항목 사용)
        location_by_id = {}
        location_by_name = {}
        def _normalize_name(s: str | None) -> str:
            if s is None:
                return ''
            try:
                # strip, lowercase, collapse whitespace
                return ' '.join(str(s).strip().lower().split())
            except Exception:
                return str(s).strip().lower()
        for _, row in locations_df.iterrows():
            try:
                loc_id = str(row['id']) if 'id' in row and row['id'] is not None else None
                loc_name = str(row['name'])
                loc_entry = {
                    'id': loc_id,
                    'name': loc_name,
                    'x': float(row['lon']),  # T-map API는 x=경도, y=위도
                    'y': float(row['lat'])
                }
                if loc_id:
                    location_by_id[loc_id] = loc_entry
                # name은 중복 가능성이 있으나 폴백 용도로 첫 매치만 사용
                norm = _normalize_name(loc_name)
                if norm and norm not in location_by_name:
                    location_by_name[norm] = loc_entry
            except (ValueError, TypeError) as e:
                print(f"위치 데이터 변환 오류: {row.get('name', '')} - {e}")
                continue

        print(f"📍 위치 딕셔너리 생성 완료: {len(location_by_id)}개 id, {len(location_by_name)}개 name(폴백)")
        
        # T-map 라우터 초기화
        tmap_router = TmapRoute()
        
        # 차량별로 경로 생성
        vehicle_routes = {}
        unique_vehicles = routes_df['Vehicle_ID'].unique()
        # depot 이름을 locations.csv의 첫 행에서 가져옴
        try:
            depot_name_from_csv = None
            if not locations_df.empty:
                depot_row = locations_df.sort_values('id').iloc[0]
                depot_name_from_csv = str(depot_row['name'])
        except Exception as _de:
            print(f"Depot 추론 실패: {_de}")
        
        for vehicle_id in unique_vehicles:
            try:
                vehicle_id = int(vehicle_id)  # 확실히 정수로 변환
                vehicle_data = routes_df[routes_df['Vehicle_ID'] == vehicle_id].copy()
                vehicle_data = vehicle_data.sort_values('Stop_Order')

                # 차량별 최종 누적 Load 계산 (optimization_routes.csv의 마지막 Cumulative_Load 값)
                try:
                    final_cum_load = int(pd.to_numeric(vehicle_data['Cumulative_Load'], errors='coerce').dropna().iloc[-1]) if not vehicle_data.empty else 0
                except Exception:
                    final_cum_load = 0
                
                # 최적화 결과의 순서를 그대로 사용 (첫=출발, 마지막=도착, 나머지=경유)
                if vehicle_data.empty or len(vehicle_data) < 2:
                    print(f"Vehicle {vehicle_id}: 유효한 경로가 없습니다.")
                    continue
                start_row = vehicle_data.iloc[0]
                end_row = vehicle_data.iloc[-1]
                start_name = str(start_row['Location_Name'])
                end_name = str(end_row['Location_Name'])
                via_names = [str(n) for n in vehicle_data.iloc[1:-1]['Location_Name'].tolist()]
                # 모드 메타데이터 계산(옵션): depot 시작/종료 여부로 추론
                inferred_mode = 'FREE_START_DEPOT_END'
                if str(start_row['Location_Type']) == 'depot' and str(end_row['Location_Type']) == 'waypoint':
                    inferred_mode = 'DEPOT_START_OPEN_END'
                elif str(start_row['Location_Type']) == 'waypoint' and str(end_row['Location_Type']) == 'depot':
                    inferred_mode = 'FREE_START_DEPOT_END'

                # optimization_routes.csv에서 Location_ID 컬럼이 있으면 우선 사용
                # start_row, end_row, via_names 객체에서 Location_ID가 있을 가능성 고려
                def extract_id_from_row(row):
                    if 'Location_ID' in row and pd.notna(row.get('Location_ID')):
                        return str(row.get('Location_ID'))
                    return None

                start_id_candidate = extract_id_from_row(start_row)
                end_id_candidate = extract_id_from_row(end_row)
                via_id_candidates = [extract_id_from_row(r) for _, r in vehicle_data.iloc[1:-1].iterrows()]

                # 위치 정보 확인 (ID 우선, name 폴백)
                def exists_in_locations(id_or_name):
                    if id_or_name is None:
                        return False
                    s = str(id_or_name)
                    # ID exact match
                    if s in location_by_id:
                        return True
                    # name normalized match
                    if _normalize_name(s) in location_by_name:
                        return True
                    return False

                if not exists_in_locations(start_id_candidate or start_name):
                    print(f"Vehicle {vehicle_id}: 출발지 '{start_id_candidate or start_name}'을 찾을 수 없습니다.")
                    continue
                if not exists_in_locations(end_id_candidate or end_name):
                    print(f"Vehicle {vehicle_id}: 도착지 '{end_id_candidate or end_name}'을 찾을 수 없습니다.")
                    continue
                missing = [n for i, n in enumerate(via_names) if not exists_in_locations(via_id_candidates[i] if i < len(via_id_candidates) else n)]
                if missing:
                    print(f"Vehicle {vehicle_id}: 경유지를 찾을 수 없습니다: {missing}")
                    continue
                
                # start/end/via를 ID 우선으로 찾고, 없으면 name 폴백
                def resolve_location_by_id_or_name(name_or_id):
                    # 우선 id로 검색
                    if name_or_id is None:
                        return None
                    s = str(name_or_id)
                    if s in location_by_id:
                        return location_by_id[s].copy()
                    norm = _normalize_name(s)
                    if norm in location_by_name:
                        return location_by_name[norm].copy()
                    return None

                start_point = resolve_location_by_id_or_name(start_id_candidate or start_name)
                end_point = resolve_location_by_id_or_name(end_id_candidate or end_name)
                via_points = []
                for i, name in enumerate(via_names):
                    candidate_id = via_id_candidates[i] if i < len(via_id_candidates) else None
                    vp = resolve_location_by_id_or_name(candidate_id or name)
                    via_points.append(vp)
                # demand 주입: routes_df의 Load 값을 name 기준으로 매칭 (동일 이름 다회 출현 가능성 낮다고 가정)
                try:
                    # name -> Load 매핑 리스트를 Stop_Order 순서로 뽑아냄
                    loads_seq = vehicle_data[['Location_Name', 'Location_Type', 'Load']].to_dict('records')
                    # 출발지/경유지/도착지 각각에 demand 세팅
                    def find_first_load(name, loc_type):
                        for rec in loads_seq:
                            if str(rec['Location_Name']) == str(name) and str(rec.get('Location_Type', '')) == str(loc_type):
                                return int(rec.get('Load', 0) or 0)
                        # 타입이 다를 수 있으니 이름만 매칭하는 폴백
                        for rec in loads_seq:
                            if str(rec['Location_Name']) == str(name):
                                return int(rec.get('Load', 0) or 0)
                        return 0
                    # 출발지(depot or waypoint)
                    start_point['demand'] = find_first_load(start_name, vehicle_data.iloc[0].get('Location_Type', ''))
                    # 경유지들(waypoint)
                    for i, vp in enumerate(via_points):
                        loc_name = via_names[i]
                        # 해당 via의 타입은 보통 waypoint
                        vp['demand'] = find_first_load(loc_name, 'waypoint')
                    # 도착지(depot or waypoint)
                    end_point['demand'] = find_first_load(end_name, vehicle_data.iloc[-1].get('Location_Type', ''))
                except Exception as _inject_e:
                    print(f"demand 주입 중 오류(V{vehicle_id}): {_inject_e}")
                
            except (ValueError, TypeError) as e:
                print(f"Vehicle ID 변환 오류: {vehicle_id} - {e}")
                continue
            
            # T-map API로 경로 생성
            try:
                print(f"Vehicle {vehicle_id} 경로 생성 중...")
                print(f"  출발지: {start_point['name']}")
                print(f"  도착지: {end_point['name']}")
                print(f"  경유지: {len(via_points)}개")
                
                # If there are intermediate via points, call T-map sequential route API.
                # If there are no via points (direct from start -> end), some T-map
                # endpoints can fail or return no geometry. In that case we create a
                # simple fallback single-leg route (LineString between start and end)
                # and estimate distance/time so the vehicle still has a usable result.
                if via_points:
                    route_result = tmap_router.get_route(
                        start_point,
                        end_point,
                        via_points,
                        searchOption=opt_search,
                        start_time=opt_start,
                        carType=opt_car,
                        viaTime=opt_via
                    )
                else:
                    # Try OSRM for single-leg routing first (road network based).
                    try:
                        route_result = tmap_router.get_route_single(start_point, end_point)
                    except Exception as e_single:
                        print(f"  ⚠️ T-map 단일 경로 API 실패, 하버사인 폴백 사용: {e_single}")
                        # Haversine fallback
                        try:
                            sx, sy = float(start_point['x']), float(start_point['y'])
                            ex, ey = float(end_point['x']), float(end_point['y'])
                        except Exception:
                            raise ValueError(f"Invalid coordinate data for vehicle {vehicle_id}")

                        from math import radians, sin, cos, atan2, sqrt

                        def haversine_meters(lon1, lat1, lon2, lat2):
                            R = 6371000.0
                            dlat = radians(lat2 - lat1)
                            dlon = radians(lon2 - lon1)
                            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                            c = 2 * atan2(sqrt(a), sqrt(1-a))
                            return R * c

                        dist_m = haversine_meters(sx, sy, ex, ey)
                        avg_speed_kmh = 40.0
                        time_s = (dist_m / 1000.0) / avg_speed_kmh * 3600.0 if dist_m > 0 else 0

                        route_result = {
                            'features': [
                                {
                                    'type': 'Feature',
                                    'geometry': {
                                        'type': 'LineString',
                                        'coordinates': [[sx, sy], [ex, ey]]
                                    },
                                    'properties': {}
                                }
                            ],
                            'properties': {
                                'totalDistance': dist_m,
                                'totalTime': time_s
                            }
                        }
                
                # 경로 데이터 처리
                if 'features' in route_result and route_result['features']:
                    # 경로 좌표 추출
                    route_coordinates = []
                    for feature in route_result['features']:
                        if feature['geometry']['type'] == 'LineString':
                            coords = feature['geometry']['coordinates']
                            route_coordinates.extend(coords)
                    
                    # 중복 좌표 제거
                    unique_coords = []
                    for coord in route_coordinates:
                        if not unique_coords or coord != unique_coords[-1]:
                            unique_coords.append(coord)
                    
                    # 실제 방문 순서: 출발지 -> 경유지들 -> 도착지
                    all_waypoints = [start_point] + via_points + [end_point]
                    
                    # 차량 경로 정보 저장
                    vehicle_routes[str(vehicle_id)] = {
                        'vehicle_id': int(vehicle_id),
                        'start_point': start_point,
                        'end_point': end_point,
                        'via_points': via_points,
                        'waypoints': all_waypoints,  # 실제 방문 순서대로
                        'route_geometry': {
                            'type': 'LineString',
                            'coordinates': unique_coords
                        },
                        'properties': route_result.get('properties', {}),
                        'total_distance': float(route_result.get('properties', {}).get('totalDistance', 0)),
                        'total_time': float(route_result.get('properties', {}).get('totalTime', 0)),
                        # 누적 Load의 최종값 (차량별)
                        'route_load': final_cum_load
                    }
                    
                    print(f"  ✅ 성공: {len(unique_coords)}개 좌표")
                    
                else:
                    print(f"  ❌ 경로 생성 실패: 응답에 경로 데이터가 없습니다.")
                    
            except Exception as route_error:
                print(f"  ❌ Vehicle {vehicle_id} 경로 생성 실패: {route_error}")
                continue
        
        # 통계 정보 계산
        try:
            total_distance = sum(
                float(route.get('total_distance', 0)) 
                for route in vehicle_routes.values()
            )
            total_time = sum(
                float(route.get('total_time', 0)) 
                for route in vehicle_routes.values()
            )
        except (ValueError, TypeError) as e:
            print(f"통계 계산 오류: {e}")
            total_distance = 0
            total_time = 0
        
        response_data = {
            'success': True,
            'vehicle_routes': vehicle_routes,
            'statistics': {
                'total_distance': f"{total_distance/1000:.1f} km" if total_distance > 0 else "N/A",
                'total_time': f"{int(total_time//60):.0f} min" if total_time > 0 else "N/A",
                'route_count': len(vehicle_routes),
                'optimization_score': f"{min(100, max(0, 100 - len(vehicle_routes) * 5)):.0f}%"
            }
        }
        
        # 📁 경로 데이터를 JSON 파일에 저장
        try:
            cache_data = {
                'generated_at': datetime.now().isoformat(),
                'vehicle_routes': vehicle_routes,
                'statistics': response_data['statistics'],
                'source_csv': {
                    'routes_file': 'optimization_routes.csv',
                    'locations_file': 'locations.csv'
                },
                'inferred_route_mode': inferred_mode if 'inferred_mode' in locals() else 'unknown'
            }
            
            with open(project_path('generated_routes.json', pid), 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 메타데이터 저장
            metadata = {
                'last_generated': datetime.now().isoformat(),
                'route_count': len(vehicle_routes),
                'total_distance_m': total_distance,
                'total_time_s': total_time
            }
            
            with open(project_path('route_metadata.json', pid), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            print(f"💾 경로 데이터 저장 완료: {project_path('generated_routes.json', pid)}")
            # If a per-project HTML report exists, remove it so next View Report regenerates it
            try:
                report_file = project_path('route_report.html', pid)
                if os.path.exists(report_file):
                    os.remove(report_file)
                    print(f"🗑️ Removed stale report for project {pid}: {report_file}")
                # also remove table report so it will be regenerated on next View Report
                try:
                    table_report = project_path('route_table_report.html', pid)
                    if os.path.exists(table_report):
                        os.remove(table_report)
                        print(f"🗑️ Removed stale table report for project {pid}: {table_report}")
                except Exception as rm_table_err:
                    print(f"⚠️ Failed to remove stale table report for project {pid}: {rm_table_err}")
            except Exception as rm_err:
                print(f"⚠️ Failed to remove stale report for project {pid}: {rm_err}")
            
        except Exception as save_error:
            print(f"⚠️ 경로 데이터 저장 실패: {save_error}")
            # 저장 실패해도 응답은 정상적으로 반환
        
        print(f"✅ 총 {len(vehicle_routes)}개 차량 경로 생성 완료")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ 경로 생성 중 오류: {e}")
        return jsonify({'error': f'경로 생성 실패: {str(e)}'}), 500

@app.route('/check-route-cache', methods=['GET'])
def check_route_cache():
    """경로 캐시 상태 확인"""
    try:
        pid = get_project_id()
        if os.path.exists(project_path('generated_routes.json', pid)) and os.path.exists(project_path('route_metadata.json', pid)):
            # 메타데이터에서 생성 시간 확인
            with open(project_path('route_metadata.json', pid), 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            return jsonify({
                'has_cache': True,
                'generated_at': metadata.get('last_generated'),
                'route_count': metadata.get('route_count', 0),
                'message': '캐시된 경로 데이터 있음'
            })
        else:
            return jsonify({
                'has_cache': False,
                'message': '캐시된 경로 데이터 없음'
            })
            
    except Exception as e:
        return jsonify({
            'has_cache': False,
            'message': f'캐시 상태 확인 오류: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True)
    # app.run(debug=True,host='192.168.0.114', port=5000)

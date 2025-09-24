import requests
import os
import json
import csv
import pandas as pd
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

TMAP_APP_KEY = os.getenv('TMAP_API_KEY')

def create_tmap_matrix(locations, transportMode="car", metric="Recommendation"):
    """
    좌표 목록을 기반으로 TMAP Matrix API를 사용하여 거리와 시간 매트릭스를 생성합니다.
    
    Args:
        locations (list): [(경도, 위도), (경도, 위도), ...] 형태의 좌표 리스트
        transportMode (str): 이동 수단 (기본값: "car", 옵션: "pedestrian")
        metric (str): 경로 탐색 옵션 (기본값: "Recommendation")
        
    Returns:
        dict: {"time_matrix": list, "distance_matrix": list} 
              시간 매트릭스 (단위: 초), 거리 매트릭스 (단위: 미터)
    """
    if not TMAP_APP_KEY:
        raise ValueError("TMAP_APP_KEY 환경 변수를 설정해주세요.")

    url = "https://apis.openapi.sk.com/tmap/matrix?version=1"
    
    headers = {
        "appKey": TMAP_APP_KEY,
        "Content-Type": "application/json"
    }
    
    # API 요청 형식에 맞게 좌표 포맷팅 (문자열로 변환)
    formatted_locations = [{"lon": str(lon), "lat": str(lat)} for lon, lat in locations]
    
    payload = {
        "origins": formatted_locations,
        "destinations": formatted_locations,
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "transportMode": transportMode,
        "metric": metric
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        
        matrix_data = response.json()
        
        # 응답에서 시간과 거리 정보 모두 추출하여 2D 리스트 생성
        matrix_routes = matrix_data.get('matrixRoutes', [])
        if not matrix_routes:
            raise ValueError("Matrix API로부터 유효한 매트릭스를 받지 못했습니다.")
        
        # 매트릭스 크기 계산 (origins/destinations 개수)
        num_locations = len(locations)
        time_matrix = [[0 for _ in range(num_locations)] for _ in range(num_locations)]
        distance_matrix = [[0 for _ in range(num_locations)] for _ in range(num_locations)]
        
        # matrixRoutes에서 시간과 거리 정보 추출
        for route in matrix_routes:
            origin_idx = route.get('originIndex')
            dest_idx = route.get('destinationIndex')
            duration = route.get('duration', 0)
            distance = route.get('distance', 0)
            
            # 경로를 찾지 못한 경우 큰 값으로 처리
            if duration <= 0 and origin_idx != dest_idx:
                duration = 9999999
            if distance <= 0 and origin_idx != dest_idx:
                distance = 9999999
                
            time_matrix[origin_idx][dest_idx] = duration
            distance_matrix[origin_idx][dest_idx] = distance

        return {
            "time_matrix": time_matrix,
            "distance_matrix": distance_matrix
        }

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during API request: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        print(f"Error parsing TMAP Matrix API response: {e}")
        if 'response' in locals():
            print(f"Response content: {response.text}")
        return None


def process_locations_data(data):
    """
    좌표 데이터 목록에서 좌표와 이름 목록을 처리합니다.
    데이터는 {'name': str, 'lon': float, 'lat': float} 형태의 딕셔너리 리스트여야 합니다.
    """
    locations = []
    location_names = []
    
    if len(data) > 30:
        raise ValueError(f"위치 데이터가 30개를 초과합니다 ({len(data)}개). TMAP Matrix API는 최대 30x30까지만 지원합니다.")

    try:
        for row in data:
            # 좌표를 float으로 변환
            lon = float(row['lon'])
            lat = float(row['lat'])
            locations.append((lon, lat))
            location_names.append(row['name'])
    except (ValueError, KeyError) as e:
        raise ValueError(f"데이터 형식 오류. 'lon', 'lat', 'name' 키를 확인하세요. ({e})")
    
    return locations, location_names


def load_locations_from_csv(file_path='locations.csv'):
    """
    CSV 파일에서 좌표 목록을 로드합니다.
    CSV는 'name', 'lon', 'lat' 헤더를 가져야 합니다.
    한글 인코딩을 자동으로 감지하여 처리합니다.
    """
    # 다양한 인코딩 시도 (한국어 파일에 자주 사용되는 순서)
    encodings_to_try = ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949', 'ascii']
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, mode='r', encoding=encoding) as infile:
                reader = csv.DictReader(infile)
                all_rows = list(reader)
                print(f"CSV 파일을 {encoding} 인코딩으로 성공적으로 로드했습니다.")
                return process_locations_data(all_rows)
        except (UnicodeDecodeError, UnicodeError):
            # 이 인코딩으로 읽을 수 없으면 다음 인코딩 시도
            continue
        except FileNotFoundError:
            print(f"오류: 파일 '{file_path}'를 찾을 수 없습니다.")
            return None, None
        except ValueError as e:
            print(f"오류: {e}")
            return None, None
        except Exception as e:
            print(f"예상치 못한 오류 ({encoding}): {e}")
            continue
    
    # 모든 인코딩을 시도했지만 실패한 경우
    print(f"오류: 파일 '{file_path}'를 지원되는 인코딩으로 읽을 수 없습니다.")
    print(f"시도한 인코딩: {', '.join(encodings_to_try)}")
    return None, None


def save_matrix_to_csv(matrix, location_names, filename='matrix_result.csv'):
    """
    매트릭스 결과를 CSV 파일로 저장합니다.
    UTF-8 인코딩으로 저장하여 한글 위치명이 깨지지 않도록 합니다.
    """
    try:
        df = pd.DataFrame(matrix, index=location_names, columns=location_names)
        df.to_csv(filename, encoding='utf-8-sig')
        print(f"매트릭스 파일 '{filename}'을 UTF-8-SIG 인코딩으로 저장했습니다.")
        return True
    except Exception as e:
        print(f"매트릭스 저장 중 오류 발생: {e}")
        return False

def save_matrices_to_csv(time_matrix, distance_matrix, location_names, 
                        time_filename='time_matrix.csv', 
                        distance_filename='distance_matrix.csv'):
    """
    시간과 거리 매트릭스 결과를 각각 CSV 파일로 저장합니다.
    UTF-8 인코딩으로 저장하여 한글 위치명이 깨지지 않도록 합니다.
    """
    try:
        # 시간 매트릭스 저장 (UTF-8 BOM과 함께)
        time_df = pd.DataFrame(time_matrix, index=location_names, columns=location_names)
        time_df.to_csv(time_filename, encoding='utf-8-sig')
        
        # 거리 매트릭스 저장 (UTF-8 BOM과 함께)
        distance_df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
        distance_df.to_csv(distance_filename, encoding='utf-8-sig')
        
        print(f"매트릭스 파일을 UTF-8-SIG 인코딩으로 저장했습니다.")
        return True
    except Exception as e:
        print(f"매트릭스 저장 중 오류 발생: {e}")
        return False


def create_matrix_from_locations(transportMode="car", metric="Recommendation",
                                locations_file: str | None = None,
                                time_filename: str | None = None,
                                distance_filename: str | None = None):
    """
    locations.csv에서 데이터를 자동으로 불러와서 매트릭스를 생성하고 저장합니다.
    
    Args:
        transportMode (str): 이동 수단 ("car" 또는 "pedestrian")
        metric (str): 경로 탐색 옵션
        
    Returns:
        dict: {"success": bool, "message": str, "matrix": list, "locations": list}
    """
    try:
        # locations.csv에서 데이터 로드 (경로 지정 가능)
        locations_csv = locations_file or 'locations.csv'
        locations, location_names = load_locations_from_csv(locations_csv)
        
        if not locations:
            return {"success": False, "message": "locations.csv 파일을 불러올 수 없습니다."}
        
        print(f"{len(locations)}개 위치에서 매트릭스 생성 중... (mode: {transportMode}, metric: {metric})")
        
        # 매트릭스 생성 (시간과 거리 모두)
        matrix_result = create_tmap_matrix(locations, transportMode, metric)
        
        if not matrix_result:
            return {"success": False, "message": "매트릭스 생성에 실패했습니다."}
        
        time_matrix = matrix_result["time_matrix"]
        distance_matrix = matrix_result["distance_matrix"]
        
        # 결과를 CSV로 저장 (두 개의 파일로 분리 저장)
        save_success = save_matrices_to_csv(
            time_matrix,
            distance_matrix,
            location_names,
            time_filename=time_filename or 'time_matrix.csv',
            distance_filename=distance_filename or 'distance_matrix.csv'
        )
        
        if save_success:
            return {
                "success": True, 
                "message": "시간과 거리 매트릭스가 성공적으로 생성되고 저장되었습니다.",
                "time_matrix": time_matrix,
                "distance_matrix": distance_matrix,
                "locations": location_names
            }
        else:
            return {
                "success": True, 
                "message": "매트릭스는 생성되었지만 저장에 실패했습니다.",
                "time_matrix": time_matrix,
                "distance_matrix": distance_matrix,
                "locations": location_names
            }
            
    except Exception as e:
        return {"success": False, "message": f"오류 발생: {str(e)}"}

if __name__ == '__main__':
    # 테스트용 실행
    result = create_matrix_from_locations("car", "Recommendation")
    print(result["message"])
    if result["success"] and "time_matrix" in result:
        print("\n위치 순서:", result["locations"])
        print("\n생성된 시간 매트릭스 (단위: 초):")
        for i, row in enumerate(result["time_matrix"]):
            print(f"{result['locations'][i]:<10}: {row}")
        print("\n생성된 거리 매트릭스 (단위: 미터):")
        for i, row in enumerate(result["distance_matrix"]):
            print(f"{result['locations'][i]:<10}: {row}")
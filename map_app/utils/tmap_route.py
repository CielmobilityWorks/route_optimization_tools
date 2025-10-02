"""
T-map API를 사용한 경유지 경로 탐색 모듈
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import urllib.parse
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# T-map API 키 설정
TMAP_APP_KEY = os.getenv('TMAP_API_KEY')


class TmapRoute:
    """T-map API를 사용한 경로 탐색 클래스"""
    
    def __init__(self, api_key: str = None):
        """TmapRoute 클래스 초기화"""
        self.api_key = api_key or TMAP_APP_KEY
        
        if not self.api_key:
            raise ValueError("T-map API 키가 설정되지 않았습니다.")
        
        self.base_url = "https://apis.openapi.sk.com/tmap/routes/routeSequential100"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "appKey": self.api_key
        }
    
    def create_route_request(self, start_point, end_point, via_points, searchOption="0", start_time=None, carType="3", viaTime="60"):
        """경로 탐색 요청 데이터 생성"""
        if start_time is None:
            start_time = datetime.now().strftime("%Y%m%d%H%M")
        
        # 경유지 데이터 구성
        formatted_via_points = []
        for i, point in enumerate(via_points):
            via_point = {
                "viaPointId": point.get('id', f'via_{i+1}'),
                "viaPointName": urllib.parse.quote(point['name'].encode('utf-8')),
                "viaX": str(point['x']),
                "viaY": str(point['y'])
            }
            if 'time' in point:
                via_point["viaTime"] = str(point['time'])
            formatted_via_points.append(via_point)
        
        return {
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "startName": urllib.parse.quote(start_point['name'].encode('utf-8')),
            "startX": str(start_point['x']),
            "startY": str(start_point['y']),
            "startTime": start_time,
            "endName": urllib.parse.quote(end_point['name'].encode('utf-8')),
            "endX": str(end_point['x']),
            "endY": str(end_point['y']),
            "searchOption": searchOption,
            "carType": carType,
            "viaPoints": formatted_via_points,
            "viaTime": viaTime
        }
    
    def get_route(self, start_point, end_point, via_points,
                  searchOption: Optional[str] = None,
                  start_time: Optional[str] = None,
                  carType: Optional[str] = None,
                  viaTime: Optional[str] = None):
        """경유지 경로 탐색 실행
        옵션 인수는 모두 문자열(또는 None)로 받아 create_route_request에 전달한다.
        """
        request_data = self.create_route_request(
            start_point,
            end_point,
            via_points,
            searchOption=searchOption if searchOption is not None else "0",
            start_time=start_time,
            carType=carType if carType is not None else "3",
            viaTime=viaTime if viaTime is not None else "60"
        )
        
        try:
            response = requests.post(
                f"{self.base_url}?version=1",
                headers=self.headers,
                json=request_data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if 'error' in result:
                raise ValueError(f"T-map API Error: {result['error']}")
            
            return result
            
        except requests.RequestException as e:
            raise requests.RequestException(f"API 요청 실패: {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"응답 파싱 실패: {str(e)}")

    def get_route_single(self, start_point, end_point, searchOption: Optional[str] = None, start_time: Optional[str] = None, carType: Optional[str] = None, viaTime: Optional[str] = None):
        """T-map 단일 구간(route API) 호출.
        start_point/end_point는 {'x': lon, 'y': lat, 'name': ...} 형태로 받습니다.
        profile: 차량 타입이나 모드에 대한 문자열로 내부에서 carType 등과 매핑해 사용 가능합니다.
        반환은 기존 후처리와 호환되도록 features/properties 구조를 만듭니다.
        참고: T-map의 단일 경로 API 문서를 따릅니다.
        """
        try:
            sx, sy = float(start_point['x']), float(start_point['y'])
            ex, ey = float(end_point['x']), float(end_point['y'])
        except Exception:
            raise ValueError('Invalid start/end coordinates for T-map single route request')

        # T-map single route endpoint (예: /route) 사용
        # 문서: https://tmapapi.tmapmobility.com/main.html#webservice/docs/tmapRouteDoc
        # 사용자 키(appKey)는 클래스 헤더에서 이미 설정됨
        single_url = "https://apis.openapi.sk.com/tmap/routes"

        # 요청 바디는 T-map 문서의 single route 형식에 맞춰 구성
        # start_time/carType/searchOption 등은 다중 경로 API와 동일한 이름으로 전달할 수 있도록 허용
        if start_time is None:
            start_time = datetime.now().strftime("%Y%m%d%H%M")

        body = {
            'startX': str(sx),
            'startY': str(sy),
            'endX': str(ex),
            'endY': str(ey),
            'reqCoordType': 'WGS84GEO',
            'resCoordType': 'WGS84GEO',
            'startName': urllib.parse.quote(start_point.get('name', '').encode('utf-8')),
            'endName': urllib.parse.quote(end_point.get('name', '').encode('utf-8')),
            'startTime': start_time,
            'carType': str(carType) if carType is not None else '3',
            'searchOption': str(searchOption) if searchOption is not None else '0'
        }
        if viaTime is not None:
            body['viaTime'] = str(viaTime)

        try:
            resp = requests.post(f"{single_url}?version=1", headers=self.headers, json=body, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise requests.RequestException(f"T-map 단일 구간 API 요청 실패: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"T-map 단일 구간 응답 파싱 실패: {e}")

        # 응답을 기존 후처리와 호환되는 형태로 간단히 포장
        # T-map single route 응답 구조에 따라 features/geometry 추출
        features = []
        total_distance = 0.0
        total_time = 0.0

        # helper: 안전하게 값을 float으로 변환
        def _to_float(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        # Try several known locations for distance/time in the response
        try:
            if isinstance(data, dict):
                # 1) Top-level properties
                props = data.get('properties')
                if isinstance(props, dict):
                    total_distance = _to_float(props.get('totalDistance') or props.get('totalDistanceM') or props.get('distance'))
                    total_time = _to_float(props.get('totalTime') or props.get('totalTimeS') or props.get('time') or props.get('duration'))

                # 2) Top-level keys
                if total_distance == 0.0:
                    total_distance = _to_float(data.get('totalDistance') or data.get('distance'))
                if total_time == 0.0:
                    total_time = _to_float(data.get('totalTime') or data.get('time') or data.get('duration'))

                # 3) If 'features' exists, use it
                if 'features' in data and isinstance(data['features'], list):
                    features = data['features']

                # 4) Some T-map responses include a 'route' or 'features' nested structure
                if not features:
                    # try possible nested structures
                    if 'route' in data and isinstance(data['route'], dict):
                        r = data['route']
                        if isinstance(r.get('features'), list):
                            features = r.get('features')
                        # route summary
                        summary = r.get('summary') or {}
                        total_distance = total_distance or _to_float(summary.get('distance') or summary.get('totalDistance'))
                        total_time = total_time or _to_float(summary.get('duration') or summary.get('totalTime'))

                # 5) Additionally, inspect each feature's properties for summary/distance/time fields
                try:
                    feats = data.get('features') if isinstance(data.get('features'), list) else []
                    if feats and not features:
                        features = feats

                    # First, prefer any feature that contains totalDistance/totalTime (e.g., summary in first point)
                    found = False
                    for feat in feats:
                        if not isinstance(feat, dict):
                            continue
                        fprops = feat.get('properties') if isinstance(feat.get('properties'), dict) else {}
                        if 'totalDistance' in fprops or 'totalTime' in fprops:
                            total_distance = total_distance or _to_float(fprops.get('totalDistance'))
                            total_time = total_time or _to_float(fprops.get('totalTime'))
                            found = True
                            break

                    # If not found, try to sum distance/time across LineString features
                    if not found:
                        dist_sum = 0.0
                        time_sum = 0.0
                        for feat in feats:
                            if not isinstance(feat, dict):
                                continue
                            fprops = feat.get('properties') if isinstance(feat.get('properties'), dict) else {}
                            dist_sum += _to_float(fprops.get('distance'))
                            time_sum += _to_float(fprops.get('time') or fprops.get('duration'))
                        if dist_sum > 0:
                            total_distance = total_distance or dist_sum
                        if time_sum > 0:
                            total_time = total_time or time_sum

                    # If still missing, inspect properties->summary inside each feature
                    if total_distance == 0.0 or total_time == 0.0:
                        for feat in feats:
                            if not isinstance(feat, dict):
                                continue
                            fprops = feat.get('properties') if isinstance(feat.get('properties'), dict) else {}
                            summary = fprops.get('summary') if isinstance(fprops.get('summary'), dict) else None
                            if isinstance(summary, dict):
                                total_distance = total_distance or _to_float(summary.get('distance') or summary.get('totalDistance'))
                                total_time = total_time or _to_float(summary.get('duration') or summary.get('totalTime'))
                            if total_distance and total_time:
                                break
                except Exception:
                    pass

        except Exception:
            # 안전하게 무시하고 폴백값 사용
            pass

        # Ensure we always provide at least a simple LineString feature
        if not features:
            features = [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[sx, sy], [ex, ey]]
                    },
                    'properties': {}
                }
            ]

        # Ensure properties contain numeric totalDistance/totalTime
        properties = {
            'totalDistance': total_distance,
            'totalTime': total_time
        }

        return {
            'features': features,
            'properties': properties
        }
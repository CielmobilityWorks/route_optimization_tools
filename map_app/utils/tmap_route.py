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

            # --- Post-process response: try to extract per-feature time/distance and
            # annotate provided waypoint dicts (start_point, via_points, end_point)
            # with 'cumulative_time' (seconds) and 'cumulative_distance' (meters)
            try:
                # Resolve features array from common locations in response
                data = result if isinstance(result, dict) else {}

                features = []
                if isinstance(data.get('features'), list):
                    features = data.get('features')
                elif isinstance(data.get('route'), dict) and isinstance(data['route'].get('features'), list):
                    features = data['route']['features']

                # helper to extract numeric time/distance from a properties dict
                def _get_time_from_props(props: dict) -> float:
                    if not isinstance(props, dict):
                        return 0.0
                    for key in ('totalTime', 'totalTimeS', 'time', 'duration'):
                        if key in props:
                            try:
                                return float(props.get(key) or 0)
                            except Exception:
                                try:
                                    return float(props.get(key, 0))
                                except Exception:
                                    return 0.0
                    # nested summary
                    if 'summary' in props and isinstance(props['summary'], dict):
                        for key in ('duration', 'totalTime', 'time'):
                            if key in props['summary']:
                                try:
                                    return float(props['summary'].get(key) or 0)
                                except Exception:
                                    return 0.0
                    return 0.0

                def _get_distance_from_props(props: dict) -> float:
                    if not isinstance(props, dict):
                        return 0.0
                    for key in ('totalDistance', 'totalDistanceM', 'distance'):
                        if key in props:
                            try:
                                return float(props.get(key) or 0)
                            except Exception:
                                return 0.0
                    if 'summary' in props and isinstance(props['summary'], dict):
                        for key in ('distance', 'totalDistance'):
                            if key in props['summary']:
                                try:
                                    return float(props['summary'].get(key) or 0)
                                except Exception:
                                    return 0.0
                    return 0.0

                # Build route_coordinates and per-feature cumulative time/distance
                route_coords = []
                feature_times = []
                feature_distances = []
                for feat in features:
                    geom = feat.get('geometry') if isinstance(feat, dict) else None
                    props = feat.get('properties') if isinstance(feat, dict) else {}
                    coords = []
                    if isinstance(geom, dict) and geom.get('type') == 'LineString' and isinstance(geom.get('coordinates'), list):
                        coords = geom.get('coordinates')
                    # append coords (keep duplicates; we'll dedupe later)
                    feature_time = _get_time_from_props(props)
                    feature_dist = _get_distance_from_props(props)
                    feature_times.append(feature_time)
                    feature_distances.append(feature_dist)
                    route_coords.append(coords)

                # Flatten coordinates sequence and compute cumulative arrays
                flat_coords = []
                for coords in route_coords:
                    for c in coords:
                        flat_coords.append(c)

                # remove consecutive duplicates
                unique_coords = []
                for c in flat_coords:
                    if not unique_coords or unique_coords[-1] != c:
                        unique_coords.append(c)

                # If no features/time info, fallback to top-level properties
                total_time = 0.0
                total_dist = 0.0
                top_props = data.get('properties') if isinstance(data.get('properties'), dict) else {}
                total_time = float(top_props.get('totalTime') or top_props.get('time') or 0) if top_props else 0.0
                total_dist = float(top_props.get('totalDistance') or top_props.get('distance') or 0) if top_props else 0.0

                # If feature_times sum is zero but top-level has total_time, distribute
                if sum(feature_times) == 0 and total_time > 0 and len(features) > 0:
                    # distribute proportional to number of coords per feature
                    counts = [max(1, len(feat.get('geometry', {}).get('coordinates', []))) if isinstance(feat.get('geometry'), dict) else 1 for feat in features]
                    total_counts = sum(counts)
                    for i, cnt in enumerate(counts):
                        feature_times[i] = total_time * (cnt / total_counts) if total_counts > 0 else 0.0
                if sum(feature_distances) == 0 and total_dist > 0 and len(features) > 0:
                    counts = [max(1, len(feat.get('geometry', {}).get('coordinates', []))) if isinstance(feat.get('geometry'), dict) else 1 for feat in features]
                    total_counts = sum(counts)
                    for i, cnt in enumerate(counts):
                        feature_distances[i] = total_dist * (cnt / total_counts) if total_counts > 0 else 0.0

                # Build cumulative lists per unique coordinate by distributing each feature's time across its internal segments
                cumulative_time_per_coord = []
                cumulative_dist_per_coord = []
                cum_time = 0.0
                cum_dist = 0.0
                for fi, coords in enumerate(route_coords):
                    if not coords:
                        continue
                    ft = float(feature_times[fi] or 0.0)
                    fd = float(feature_distances[fi] or 0.0)
                    seg_count = max(1, len(coords) - 1)
                    time_per_seg = ft / seg_count if seg_count > 0 else 0.0
                    dist_per_seg = fd / seg_count if seg_count > 0 else 0.0
                    for idx_in_feat, _coord in enumerate(coords):
                        # avoid duplicating the first coordinate of a feature if it's the same as last of unique_coords
                        if cumulative_time_per_coord and _coord == unique_coords[len(cumulative_time_per_coord)-1]:
                            continue
                        cumulative_time_per_coord.append(cum_time)
                        cumulative_dist_per_coord.append(cum_dist)
                        if idx_in_feat < seg_count:
                            cum_time += time_per_seg
                            cum_dist += dist_per_seg

                # Ensure final coordinate has final totals
                if cumulative_time_per_coord and (len(cumulative_time_per_coord) < len(unique_coords)):
                    # pad remaining with final cum values
                    while len(cumulative_time_per_coord) < len(unique_coords):
                        cumulative_time_per_coord.append(cum_time)
                        cumulative_dist_per_coord.append(cum_dist)

                # Find nearest coordinate index helper (euclidean approx)
                def _closest_index(coord_list, target):
                    if not coord_list or not target:
                        return 0
                    tx, ty = float(target[0]), float(target[1])
                    best_i = 0
                    best_d = float('inf')
                    for i, c in enumerate(coord_list):
                        try:
                            dx = float(c[0]) - tx
                            dy = float(c[1]) - ty
                            d = dx*dx + dy*dy
                            if d < best_d:
                                best_d = d
                                best_i = i
                        except Exception:
                            continue
                    return best_i

                # Annotate waypoints (in-place) with cumulative_time/cumulative_distance
                all_points = [start_point] + list(via_points or []) + [end_point]
                if unique_coords and cumulative_time_per_coord:
                    last_index = 0  # Track last matched index to ensure sequential matching
                    for i, wp in enumerate(all_points):
                        try:
                            tx = wp.get('x')
                            ty = wp.get('y')
                            if tx is None or ty is None:
                                continue
                            
                            # Determine search range based on waypoint position
                            if i == 0:
                                # Start point: search in first 20% of route
                                search_start = 0
                                search_end = max(1, int(len(unique_coords) * 0.2))
                            elif i == len(all_points) - 1:
                                # End point: search in last 20% of route
                                search_start = max(last_index, int(len(unique_coords) * 0.8))
                                search_end = len(unique_coords)
                            else:
                                # Via points: search from last index to end
                                search_start = last_index
                                search_end = len(unique_coords)
                            
                            # Find nearest coordinate in the search range
                            best_i = search_start
                            best_d = float('inf')
                            for j in range(search_start, min(search_end, len(unique_coords))):
                                try:
                                    c = unique_coords[j]
                                    dx = float(c[0]) - tx
                                    dy = float(c[1]) - ty
                                    d = dx*dx + dy*dy
                                    if d < best_d:
                                        best_d = d
                                        best_i = j
                                except Exception:
                                    continue
                            
                            nearest = best_i
                            last_index = nearest  # Update for next waypoint
                            
                            # guard index range
                            if nearest < 0:
                                nearest = 0
                            if nearest >= len(cumulative_time_per_coord):
                                nearest = len(cumulative_time_per_coord) - 1
                            wp['cumulative_time'] = float(cumulative_time_per_coord[nearest])
                            wp['cumulative_distance'] = float(cumulative_dist_per_coord[nearest])
                            # if start_time provided in YYYYMMDDHHMM format, compute ISO arrival time
                            if start_time and isinstance(start_time, str) and len(start_time) >= 12:
                                try:
                                    from datetime import datetime, timedelta
                                    # try parse common format YYYYMMDDHHMM
                                    start_dt = datetime.strptime(start_time[:12], '%Y%m%d%H%M')
                                    arrival_dt = start_dt + timedelta(seconds=float(wp['cumulative_time'] or 0))
                                    wp['arrival_time'] = arrival_dt.isoformat()
                                except Exception:
                                    # ignore parsing errors
                                    pass
                        except Exception:
                            continue

            except Exception as _post_e:
                # non-fatal: if post-processing fails, still return raw result
                print(f"⚠️ Tmap response post-processing warning: {_post_e}")

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


def get_route_with_order(ordered_locations: List[Dict]) -> Optional[Dict]:
    """
    순서가 정해진 locations를 받아서 TMAP API로 경로를 계산합니다.
    
    Args:
        ordered_locations: 순서대로 정렬된 location 리스트
                          각 location은 {'name', 'lat', 'lng', 'demand', 'type'} 형식
    
    Returns:
        경로 정보를 포함한 딕셔너리 또는 None
        {
            'waypoints': [...],  # cumulative_distance, cumulative_time 포함
            'total_distance': float,
            'total_time': float,
            'geometry': {...}
        }
    """
    try:
        if len(ordered_locations) < 2:
            print("⚠️ 최소 2개의 location이 필요합니다")
            return None
        
        tmap_route = TmapRoute()
        
        # 시작점과 종료점 설정
        start_loc = ordered_locations[0]
        end_loc = ordered_locations[-1]
        
        start_point = {
            'name': start_loc['name'],
            'x': start_loc['lng'],
            'y': start_loc['lat']
        }
        
        end_point = {
            'name': end_loc['name'],
            'x': end_loc['lng'],
            'y': end_loc['lat']
        }
        
        # 중간 경유지 (시작과 끝 제외)
        via_points = []
        for i, loc in enumerate(ordered_locations[1:-1], 1):
            via_points.append({
                'id': f'via_{i}',
                'name': loc['name'],
                'x': loc['lng'],
                'y': loc['lat']
            })
        
        # TMAP API 호출
        print(f"🗺️ TMAP API 호출: {start_point['name']} -> ... -> {end_point['name']} (경유지 {len(via_points)}개)")
        
        route_result = tmap_route.get_route(
            start_point=start_point,
            end_point=end_point,
            via_points=via_points,
            searchOption="0",  # 추천 경로
            carType="3",       # 승용차
            viaTime="60"       # 경유지당 1분
        )
        
        if not route_result:
            print("❌ TMAP API 응답 없음")
            return None
        
        # 응답 파싱
        features = route_result.get('features', [])
        properties = route_result.get('properties', {})
        
        total_distance = properties.get('totalDistance', 0)
        total_time = properties.get('totalTime', 0)
        
        # Waypoints 생성 (cumulative 값 계산)
        waypoints = []
        cumulative_distance = 0
        cumulative_time = 0
        
        for i, loc in enumerate(ordered_locations):
            # 각 구간의 거리와 시간 추출 (feature에서)
            segment_distance = 0
            segment_time = 0
            
            if i > 0 and i <= len(features):
                # 이전 waypoint에서 현재까지의 구간
                feature = features[i-1] if i-1 < len(features) else {}
                if isinstance(feature, dict):
                    feat_props = feature.get('properties', {})
                    segment_distance = feat_props.get('distance', 0) or feat_props.get('totalDistance', 0)
                    segment_time = feat_props.get('time', 0) or feat_props.get('totalTime', 0)
            
            cumulative_distance += segment_distance
            cumulative_time += segment_time
            
            waypoint = {
                'name': loc['name'],
                'location': [loc['lng'], loc['lat']],
                'type': loc.get('type', 'customer'),
                'demand': loc.get('demand', 0),
                'cumulative_distance': cumulative_distance,
                'cumulative_time': cumulative_time,
                'segment_distance': segment_distance,
                'segment_time': segment_time
            }
            
            waypoints.append(waypoint)
        
        # 마지막 waypoint의 cumulative 값으로 total 값 조정
        if waypoints:
            last_wp = waypoints[-1]
            if total_distance == 0:
                total_distance = last_wp['cumulative_distance']
            if total_time == 0:
                total_time = last_wp['cumulative_time']
        
        result = {
            'waypoints': waypoints,
            'total_distance': total_distance,
            'total_time': total_time,
            'geometry': {
                'type': 'FeatureCollection',
                'features': features
            }
        }
        
        print(f"✅ 경로 계산 완료: {total_distance}m, {total_time}s")
        return result
        
    except Exception as e:
        print(f"❌ get_route_with_order 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
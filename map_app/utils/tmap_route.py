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

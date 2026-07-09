import os
import sys

# Path adjustment for standalone execution
if __name__ == "__main__" or "core" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import re
import urllib3
import hmac
import hashlib
import base64
import time
import uuid
from urllib.parse import urlencode, quote
from collections import OrderedDict
from curl_cffi import requests as requests_cffi

from core.config import Config

class NaverPlaceScraper:
    def __init__(self):
        self.session = requests_cffi.Session(impersonate="chrome110")
        self.hmac_key = Config.get_hmac_key()
        self.app_version = "6.5.2.1"
        self.user_agent = f"NaverMap/{self.app_version} (Android 13; SM-G998N)"

    def parse_id(self, input_value):
        """URL 또는 문자열에서 숫자 ID만 추출"""
        input_value = input_value.strip()
        if not input_value: return None
        match = re.search(r'(\d+)', input_value.split('/')[-1]) or re.search(r'(\d+)', input_value)
        return match.group(1) if match else None

    def _generate_hmac(self, url):
        """네이버 지도 모바일 API용 HMAC 서명 생성"""
        timestamp_ms = int(time.time() * 1000)
        msgpad = str(timestamp_ms)
        message = (url[:255] + msgpad).encode('utf-8')
        h = hmac.new(self.hmac_key, message, hashlib.sha1)
        return msgpad, base64.b64encode(h.digest()).decode('utf-8')

    def _mobile_search(self, query, lat="37.5665", lng="126.9780", timeout=10):
        """HMAC 서명을 포함한 모바일 앱 방식 검색 API 호출"""
        base_url = "https://apis.naver.com/mapmobileapps/maps-search/instantSearchV2"
        params = OrderedDict([
            ("screenid", "SCH.instant"),
            ("caller", f"android_NaverMap_{self.app_version}"),
            ("types", "place,address,bus"),
            ("onlyBookable", "false"),
            ("query", query),
            ("lang", "ko"),
            ("coords", f"{lat},{lng}")
        ])
        
        temp_url = base_url + "?" + urlencode(params, quote_via=quote)
        msgpad, md = self._generate_hmac(temp_url)
        params['msgpad'] = msgpad
        params['md'] = md
        
        final_url = base_url + "?" + urlencode(params, quote_via=quote)
        headers = {
            "x-adid": str(uuid.uuid4()),
            "referer": "client://NaverMap",
            "user-agent": self.user_agent,
            "uuid": uuid.uuid4().hex
        }
        
        try:
            resp = self.session.get(final_url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.status_code}
        except Exception as e:
            return {"error": str(e)}

    def fetch_place_info(self, place_id):
        """
        1. directionsPOI API를 사용하여 고유 ID 기준으로 존재 여부 및 상호명/주소 확인
        2. 모바일 앱 방식 검색 API(instantSearchV2)를 통해 위경도 좌표(lat, lng) 추출
        """
        poi_url = f"https://map.naver.com/p/api/place/directionsPOI/{place_id}"
        poi_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://map.naver.com/"}
        
        try:
            res_poi = requests.get(poi_url, headers=poi_headers, timeout=10)
            if res_poi.status_code != 200:
                return {"error": "poi_fail", "message": f"POI API 오류 ({res_poi.status_code})", "status_code": res_poi.status_code}
            json_data = res_poi.json() or {}
            data_obj = json_data.get("data") or {}
            poi_data = data_obj.get("placeDetail") or {}
            name = poi_data.get("name")
            addr_info = poi_data.get("address") or {}
            road_addr = addr_info.get("roadAddress")
            addr = addr_info.get("address")
            
            if not name:
                return {"error": "no_name", "message": "장소 이름을 찾을 수 없음"}

            lat = None
            lng = None
            final_addr = road_addr or addr or ""
            
            # 모바일 앱 검색 API (instantSearchV2)를 이용해 좌표 확보
            search_res = self._mobile_search(name)
            places = search_res.get("place", [])
            match = next((p for p in places if p.get("id") == place_id), None)
            
            if match:
                lat = float(match.get("y") or 0)
                lng = float(match.get("x") or 0)
                short_addr_list = match.get("shortAddress", [])
                if isinstance(short_addr_list, list) and short_addr_list:
                    final_addr = " ".join(short_addr_list)
                else:
                    final_addr = match.get("roadAddress") or match.get("jibunAddress") or final_addr
            else:
                # 상호명 검색 매칭에 실패했어도 directionsPOI에서 이름이 나왔으므로 생존한 플레이스임.
                # 주소 지오코딩으로 위경도 좌표 백업 추출
                if addr:
                    addr_res = self._mobile_search(addr)
                    addr_list = addr_res.get("address", [])
                    if addr_list:
                        lat = float(addr_list[0].get('y') or 0.0)
                        lng = float(addr_list[0].get('x') or 0.0)

            if lat is None or lng is None:
                lat = 0.0
                lng = 0.0
                
            return {
                "id": place_id,
                "name": name,
                "address": final_addr,
                "original_address": addr or road_addr or "",
                "lng": lng,
                "lat": lat
            }

        except Exception as e:
            return {"error": "exception", "message": str(e)}

    def _clean_address(self, address):
        """주소의 첫 번째 토막(도 단위) 제거"""
        if not address: return address
        parts = address.strip().split(' ')
        if len(parts) > 1:
            return ' '.join(parts[1:]).strip()
        return address

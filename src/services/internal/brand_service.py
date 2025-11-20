import aiohttp
from typing import Optional

# Utils
from utils.log_utils import LogUtil

# Models
from models.response.brand.brand_info import BrandInfo

class BrandService:
    def __init__(self, log_util: LogUtil):
        self.remote_brand_service = "http://143.244.131.181:8012/client/data/fetch"
        self.log_util = log_util
    
    async def get_brand_info(self, brand_id: int) -> Optional[BrandInfo]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.remote_brand_service}/{brand_id}") as response:
                if response.status != 200:
                    return None
                brand_info_data = await response.json()
                brand_info: BrandInfo = BrandInfo(**brand_info_data)
                return brand_info
        return None

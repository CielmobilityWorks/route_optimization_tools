import sys
import unittest
from unittest.mock import Mock, patch

# 프로젝트 의존성이 테스트 환경에 설치되지 않은 경우를 대비해 최소한의 모듈 스텁을 제공합니다.
sys.modules.setdefault('requests', Mock())
mock_pandas = Mock()
mock_pandas.DataFrame = Mock()
sys.modules.setdefault('pandas', mock_pandas)
mock_dotenv = Mock()
mock_dotenv.load_dotenv = Mock()
sys.modules.setdefault('dotenv', mock_dotenv)

from map_app.utils import tmap_utils


class TestTmapUtils(unittest.TestCase):
    def setUp(self):
        self.tmap_key_patcher = patch('map_app.utils.tmap_utils.TMAP_APP_KEY', 'dummy-key')
        self.tmap_key_patcher.start()

    def tearDown(self):
        self.tmap_key_patcher.stop()

    def test_process_locations_data_allows_more_than_30(self):
        data = [
            {"name": f"loc{i}", "lon": i, "lat": i + 0.5}
            for i in range(35)
        ]

        locations, names = tmap_utils.process_locations_data(data)

        self.assertEqual(len(locations), 35)
        self.assertEqual(len(names), 35)
        self.assertEqual(locations[0], (0.0, 0.5))
        self.assertEqual(names[-1], "loc34")

    @patch('map_app.utils.tmap_utils.requests.post')
    def test_create_tmap_matrix_single_block(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "matrixRoutes": [
                {"originIndex": 0, "destinationIndex": 0, "duration": 1, "distance": 10},
                {"originIndex": 0, "destinationIndex": 1, "duration": 2, "distance": 20},
                {"originIndex": 1, "destinationIndex": 0, "duration": 3, "distance": 30},
                {"originIndex": 1, "destinationIndex": 1, "duration": 4, "distance": 40},
            ]
        }
        mock_post.return_value = mock_response

        locations = [(127.0, 37.0), (127.1, 37.1)]

        result = tmap_utils.create_tmap_matrix(locations)

        self.assertEqual(result["time_matrix"], [[1, 2], [3, 4]])
        self.assertEqual(result["distance_matrix"], [[10, 20], [30, 40]])
        mock_post.assert_called_once()

    @patch('map_app.utils.tmap_utils.create_tmap_matrix')
    def test_create_tmap_matrix_batched_combines_blocks(self, mock_single_block):
        locations = [(float(i), float(i)) for i in range(35)]

        def fake_create_block(origin_block, transportMode='car', metric='Recommendation', destinations=None):
            dest_block = destinations or origin_block
            origin_indices = [int(round(coord[0])) for coord in origin_block]
            dest_indices = [int(round(coord[0])) for coord in dest_block]

            time_matrix = [
                [origin_idx * 100 + dest_idx for dest_idx in dest_indices]
                for origin_idx in origin_indices
            ]
            distance_matrix = [
                [origin_idx * 100 + dest_idx for dest_idx in dest_indices]
                for origin_idx in origin_indices
            ]
            return {"time_matrix": time_matrix, "distance_matrix": distance_matrix}

        mock_single_block.side_effect = fake_create_block

        result = tmap_utils.create_tmap_matrix_batched(locations, batch_size=30)

        self.assertEqual(len(result["time_matrix"]), len(locations))
        self.assertEqual(len(result["time_matrix"][0]), len(locations))
        self.assertEqual(result["time_matrix"][0][34], 34)
        self.assertEqual(result["time_matrix"][34][0], 3400)
        self.assertEqual(mock_single_block.call_count, 4)

    @patch('map_app.utils.tmap_utils.create_tmap_matrix')
    def test_create_tmap_matrix_batched_single_block_passthrough(self, mock_single_block):
        mock_single_block.return_value = {"time_matrix": [[0]], "distance_matrix": [[0]]}

        result = tmap_utils.create_tmap_matrix_batched([(0.0, 0.0)], batch_size=30)

        self.assertEqual(result["time_matrix"], [[0]])
        self.assertEqual(result["distance_matrix"], [[0]])
        mock_single_block.assert_called_once()
        args, kwargs = mock_single_block.call_args
        self.assertEqual(args[0], [(0.0, 0.0)])
        self.assertEqual(kwargs, {'transportMode': 'car', 'metric': 'Recommendation'})


if __name__ == '__main__':
    unittest.main()

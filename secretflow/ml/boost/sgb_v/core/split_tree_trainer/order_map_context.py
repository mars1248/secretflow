# Copyright 2023 Ant Group Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import math
from typing import List, Tuple

import numpy as np


# Deal with order map context of a single partition
class OrderMapContext:
    """Manage context related to order map, and bucket and split point information derived from it."""

    def __init__(self):
        self.order_map = None
        self.split_points = None
        self.feature_buckets = None
        self.features = None
        self.buckets = None

    def _qcut(self, x: np.ndarray) -> Tuple[np.ndarray, List]:
        sorted_x = np.sort(x, axis=0)
        remained_count = len(sorted_x)
        assert remained_count > 0, 'can not qcut empty x'

        value_category = list()
        last_value = None

        split_points = list()
        expected_bin_count = math.ceil(remained_count / self.buckets)
        current_bin_count = 0
        for v in sorted_x:
            if v != last_value:
                if len(value_category) <= self.buckets:
                    value_category.append(v)

                if current_bin_count >= expected_bin_count:
                    split_points.append(v)
                    if len(split_points) == self.buckets - 1:
                        break
                    remained_count -= current_bin_count
                    expected_bin_count = math.ceil(
                        remained_count / (self.buckets - len(split_points))
                    )
                    current_bin_count = 0

                last_value = v
            current_bin_count += 1

        if len(value_category) <= self.buckets:
            # full dataset category count <= buckets
            # use category as split point.
            split_points = value_category[1:]
        elif split_points[-1] != sorted_x[-1]:
            # add max sample value into split_points like xgboost.
            split_points.append(sorted_x[-1])

        split_points = list(map(float, split_points))

        def upper_bound_bin(x: float):
            count = len(split_points)
            pos = 0
            while count > 0:
                step = math.floor(count / 2)
                v = split_points[pos + step]
                if x == v:
                    return pos + step + 1
                elif x > v:
                    pos = pos + step + 1
                    count -= step + 1
                else:
                    count = step
            return pos

        bins = np.vectorize(upper_bound_bin)(x)

        return bins, split_points

    def build_maps(self, x: np.ndarray, buckets: int) -> None:
        """
        split features into buckets and build maps use in train.

        Args:
            x: dataset from this partition.

        Return:
            leaf nodes' selects
        """
        # order_map: record sample belong to which bucket of all features.
        self.order_map = np.zeros((x.shape[0], x.shape[1]), dtype=np.int8)
        # split_points: bucket split points for all features.
        self.split_points = []
        # feature_buckets: how many buckets in each feature.
        self.feature_buckets = []
        # features: how many features in dataset.
        self.features = x.shape[1]
        self.buckets = buckets

        for f in range(x.shape[1]):
            bins, split_point = self._qcut(x[:, f])
            self.order_map[:, f] = bins
            total_buckets = len(split_point)
            while total_buckets <= self.buckets:
                total_buckets += 1
                split_point.append(float('inf'))
            self.feature_buckets.append(total_buckets)
            self.split_points.append(split_point)

        self.order_map_shape = self.order_map.shape

    def get_order_map(self) -> np.ndarray:
        return self.order_map

    def get_features(self) -> int:
        return self.features

    def get_feature_buckets(self) -> List[int]:
        return self.feature_buckets

    def get_feature_bucket_at(self, index: int) -> int:
        return self.feature_buckets[index]

    def get_split_points(self) -> List[List[float]]:
        return self.split_points

    def get_order_map_shape(self) -> Tuple[int, int]:
        return self.order_map_shape

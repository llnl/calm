import numpy as np

from calm.slab.oriented._primitive import _primitive_surface_triplet_from_m


def test_exact_triplet_exhaustive_small_and_sign_variants():
    rng = range(-4, 5)
    for a in rng:
        for b in rng:
            for c in rng:
                if a == 0 and b == 0 and c == 0:
                    continue
                m = np.array([a, b, c], dtype=int)
                if np.gcd.reduce(np.abs(m)) != 1:
                    continue
                u, v, w = _primitive_surface_triplet_from_m(m)
                assert int(np.dot(m, u)) == 0
                assert int(np.dot(m, v)) == 0
                cross_uv = np.cross(u, v)
                assert np.array_equal(cross_uv, m) or np.array_equal(cross_uv, -m)
                assert int(np.dot(m, w)) == 1
                assert abs(int(np.dot(np.cross(u, v), w))) == 1


def test_exact_triplet_large_cases():
    for m in [
        np.array([101, 67, 43]),
        np.array([-137, 89, 55]),
        np.array([233, -144, 89]),
        np.array([377, 233, -144]),
    ]:
        u, v, w = _primitive_surface_triplet_from_m(m)
        assert int(np.dot(m, u)) == 0
        assert int(np.dot(m, v)) == 0
        cross_uv = np.cross(u, v)
        assert np.array_equal(cross_uv, m) or np.array_equal(cross_uv, -m)
        assert int(np.dot(m, w)) == 1
        assert abs(int(np.dot(np.cross(u, v), w))) == 1

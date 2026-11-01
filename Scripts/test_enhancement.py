"""Small authoring checks; run in Blender's bundled Python or an environment with NumPy."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from generate_enhancement import atomic_json, choose_material, face_channels, parameters


def rejected(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Invalid input was accepted")


def main():
    # Continuous coordinates, not UV-neighbour distances, define the light boundary.
    y, x = np.mgrid[0:1:513j, 0:1:513j]
    coordinates = np.stack((x, y, np.ones_like(x)), axis=2)
    channels = face_channels(coordinates, (0.5, 0.44))
    assert np.isfinite(channels).all() and channels.min() >= 0 and channels.max() <= 1
    assert np.allclose(channels[:, :, 0], channels[:, ::-1, 1])
    assert np.all(np.diff(channels[:, :, 0], axis=1) >= 0)
    assert set(np.unique(channels[:, :, 3])) == {0, 1}, "Nose shadow is a hard mask"
    nose_y, nose_x = np.where(channels[:, :, 3] == 0)
    assert len(nose_x) > 20 and (nose_x.max() - nose_x.min()) < 0.04 * x.shape[1]
    assert (nose_y.max() - nose_y.min()) < 0.1 * y.shape[0]
    assert abs(nose_x.mean() / 512 - 0.5) < 0.003
    assert abs(nose_y.mean() / 512 - 0.455) < 0.003
    disconnected = np.concatenate((coordinates[:, :200], np.zeros_like(coordinates[:, :10]), coordinates[:, :200]), axis=1)
    result = face_channels(disconnected, (0.5, 0.44))
    assert np.array_equal(result[:, :200], result[:, -200:])
    assert np.all(result[:, 200:210, 2:] == 1), "Empty UV space cannot create nose ink/shadow"
    legacy = np.concatenate((channels[:, :, :3], np.ones_like(channels[:, :, 3:])), axis=2)
    assert not (1 - legacy[:, :, 3]).any(), "RGB profiles have opaque alpha and no added nose shadow"
    rejected(lambda: face_channels(np.full((2, 2, 3), np.nan), (0.5, 0.5)))
    rejected(lambda: face_channels(coordinates, (float('inf'), 0.5)))

    def material(name, alpha=1):
        return SimpleNamespace(name=name, vertex_count=300, diffuse=(1, 1, 1, alpha))
    model = SimpleNamespace(materials=[material('body'), material('顔'), material('face', 0)])
    assert choose_material(model)[0] == 1
    model.materials.append(material('face'))
    assert choose_material(model)[0] is None, "Ambiguous visible faces require user selection"
    assert choose_material(model, index=3)[0] == 3
    rejected(lambda: choose_material(model, index=2))
    rejected(lambda: choose_material(model, index=100))
    model.materials.append(material('face'))
    rejected(lambda: choose_material(model, name='face'))
    assert parameters(None) == {'resolution': 512}
    with tempfile.TemporaryDirectory(prefix='honkai-worker-test-') as directory:
        path = Path(directory) / 'parameters.json'
        for invalid in ({'resolution': True}, {'resolution': 32768}, {'unknown': 1}, []):
            path.write_text(json.dumps(invalid), encoding='utf-8')
            rejected(lambda: parameters(path))
        path.write_text('{"resolution":256}', encoding='utf-8')
        assert parameters(path)['resolution'] == 256
        original_replace = Path.replace
        attempts = []
        def briefly_locked(source, destination):
            attempts.append(1)
            if len(attempts) < 3:
                assert json.loads(destination.read_text(encoding='utf-8')) == {'resolution': 256}
                raise PermissionError('temporary reader lock')
            return original_replace(source, destination)
        with patch.object(Path, 'replace', briefly_locked):
            atomic_json(path, {'state': 'succeeded'})
        assert len(attempts) == 3 and json.loads(path.read_text(encoding='utf-8'))['state'] == 'succeeded'
    print('PASS: face thresholds, hard nose mask, packed-channel fallback, material ambiguity and parameter bounds')


if __name__ == '__main__':
    main()

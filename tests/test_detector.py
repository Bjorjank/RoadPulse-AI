import numpy as np

from roadpulse.detection.yolox import postprocess, preprocess


def test_preprocess_bgr_top_left():
    frame = np.full((100, 200, 3), (1, 2, 3), np.uint8)
    tensor, scale = preprocess(frame, (416, 416))
    assert tensor.shape == (1, 3, 416, 416)
    assert scale == 2.08
    assert tensor[0, :, 0, 0].tolist() == [1, 2, 3]
    assert tensor[0, :, 415, 415].tolist() == [114, 114, 114]


def test_raw_tensor_decode_and_nms():
    raw = np.zeros((1, 3549, 85), np.float32)
    raw[0, 0, :4] = [10, 10, np.log(4), np.log(4)]
    raw[0, 0, 4] = 0.9
    raw[0, 0, 7] = 0.8  # COCO car index 2
    detections = postprocess(raw, (416, 416), 1, (416, 416, 3))
    assert detections.class_id.tolist() == [2]
    np.testing.assert_allclose(detections.xyxy[0], [64, 64, 96, 96], atol=0.001)
    assert abs(detections.confidence[0] - 0.72) < 0.001


def test_empty_tensor():
    assert len(postprocess(np.zeros((1, 3549, 85), np.float32), (416, 416), 1, (416, 416, 3))) == 0


def test_cross_class_overlapping_proposals_suppressed():
    raw = np.zeros((1, 3549, 85), np.float32)
    raw[0, 0, :4] = [10, 10, np.log(4), np.log(4)]
    raw[0, 1, :4] = [9, 10, np.log(4), np.log(4)]
    raw[0, 0, 4] = 0.9
    raw[0, 0, 7] = 0.9
    raw[0, 1, 4] = 0.9
    raw[0, 1, 12] = 0.8
    detections = postprocess(raw, (416, 416), 1, (416, 416, 3))
    assert len(detections) == 1
    assert detections.class_id.tolist() == [2]


def test_current_tracker_accepts_empty_detections():
    import supervision as sv
    from trackers import ByteTrackTracker

    tracked = ByteTrackTracker().update(sv.Detections.empty())
    assert len(tracked) == 0
    assert tracked.tracker_id is not None

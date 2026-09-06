from __future__ import annotations

from types import SimpleNamespace as NS

from dualforge.export.unity_skin import (
    _euler_to_quat,
    animation_tracks,
    bind_poses,
    blend_shapes,
    clip_summary,
    joint_positions,
    skin_data,
)


def _skin_entry(i0, w0, i1, w1, i2, w2, i3, w3):
    return NS(
        boneIndex_0_=i0, weight_0_=w0,
        boneIndex_1_=i1, weight_1_=w1,
        boneIndex_2_=i2, weight_2_=w2,
        boneIndex_3_=i3, weight_3_=w3,
    )


def _mat(trans=(0, 0, 0)):
    data = {f"e{r}{c}": (1.0 if r == c else 0.0) for r in range(4) for c in range(4)}
    data["e03"], data["e13"], data["e23"] = trans
    return NS(**data)


def _v3(x, y, z):
    return NS(x=x, y=y, z=z)


def _keyframe(t, value):
    return NS(time=t, value=value)


def test_skin_data_quad_weights():
    mesh = NS(m_Skin=[_skin_entry(0, 0.5, 1, 0.3, 2, 0.1, 3, 0.1)] * 4)
    joints, weights = skin_data(mesh)
    assert joints == [[0, 1, 2, 3]] * 4
    assert weights == [[0.5, 0.3, 0.1, 0.1]] * 4


def test_skin_data_none():
    assert skin_data(NS(m_Skin=None)) is None


def test_bind_poses_and_joint_positions():
    mesh = NS(
        m_BindPose=[
            _mat((1, 0, 0)),
            _mat((0, 2, 0)),
            _mat((0, 3, 0)),
        ]
    )
    poses = bind_poses(mesh)
    assert poses[0][0] == 1.0 and poses[0][15] == 1.0
    points = joint_positions(poses)
    assert points[1] == [0.0, 2.0, 0.0]
    assert points[2] == [0.0, 3.0, 0.0]


def test_blend_shapes_dense_deltas():
    vertex = NS(index=0, vertex=_v3(0, 0.1, 0), normal=_v3(0, 1, 0))
    shape = NS(name="Smile", firstVertex=0, vertexCount=1)
    mesh = NS(
        m_Shapes=NS(shapes=[shape], vertices=[]),
        m_ShapeVertices=[vertex],
    )
    targets = blend_shapes(mesh, 4)
    assert len(targets) == 1
    assert targets[0]["name"] == "Smile"
    assert targets[0]["positions"][0] == [0.0, 0.1, 0.0]
    assert targets[0]["positions"][3] == [0.0, 0.0, 0.0]
    assert targets[0]["normals"][0] == [0.0, 1.0, 0.0]


def test_blend_shapes_old_layout_without_shape_vertices():
    vertex = NS(index=2, position=_v3(1, 0, 0), normal=_v3(0, 0, 1))
    shape = NS(firstVertex=0, vertexCount=1, name="Brow")
    data = NS(shapes=[shape], vertices=[vertex])
    mesh = NS(m_Shapes=data)
    targets = blend_shapes(mesh, 4)
    assert targets[0]["positions"][2] == [1.0, 0.0, 0.0]
    assert targets[0]["normals"][2] == [0.0, 0.0, 1.0]


def test_blend_shapes_empty():
    assert blend_shapes(NS(m_Shapes=None), 4) == []


def test_animation_tracks_smoke():
    clip = NS(
        m_Name="Idle",
        m_SampleRate=60,
        m_PositionCurves=[
            NS(path="Root/Hips", curve=NS(m_Curve=[_keyframe(0.0, _v3(0, 0, 0))]))
        ],
        m_RotationCurves=[
            NS(path="Hips/Spine", curve=NS(m_Curve=[_keyframe(0.0, NS(x=0, y=0, z=0, w=1))]))
        ],
        m_ScaleCurves=[
            NS(path="Hips", curve=NS(m_Curve=[_keyframe(1.0, _v3(1, 1, 1))]))
        ],
        m_EulerCurves=None,
    )
    tracks = animation_tracks(clip)
    assert set(tracks["Hips"].keys()) == {"translation", "scale"}
    assert "rotation" in tracks["Spine"]
    assert tracks["Hips"]["translation"][0][1] == [0.0, 0.0, 0.0]
    summary = clip_summary(clip)
    assert summary["Keyframes"] == "3"


def test_clip_summary_empty():
    clip = NS(
        m_Name="Empty",
        m_PositionCurves=[], m_RotationCurves=[], m_ScaleCurves=[],
        m_SampleRate=0,
    )
    summary = clip_summary(clip)
    assert summary["Keyframes"] == "0"


def test_euler_to_quat_90_x():
    import math

    quat = _euler_to_quat([90, 0, 0])
    assert quat == [math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]
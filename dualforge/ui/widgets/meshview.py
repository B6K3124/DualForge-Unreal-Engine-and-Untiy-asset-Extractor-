from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QMatrix4x4, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFunctions_3_3_Core,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

try:
    QSurfaceFormat()
    _GL_AVAILABLE = True
except Exception:  # pragma: no cover
    _GL_AVAILABLE = False


def gl_available() -> bool:
    return _GL_AVAILABLE


_VERTEX_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uMvp;
uniform mat4 uModelView;
out vec3 vNormal;
void main() {
    vNormal = mat3(uModelView) * aNormal;
    gl_Position = uMvp * vec4(aPos, 1.0);
}
"""

_FRAGMENT_SRC = """
#version 330 core
in vec3 vNormal;
uniform vec4 uColor;
uniform float uWireframe;
out vec4 fragColor;
void main() {
    vec3 lightDir = normalize(vec3(0.35, 0.6, 0.7));
    vec3 n = normalize(vNormal);
    float diffuse = max(dot(n, lightDir), 0.15);
    vec4 color = vec4(uColor.rgb * diffuse, uColor.a);
    if (uWireframe > 0.5) {
        color = uColor;
    }
    fragColor = color;
}
"""


class MeshView(QOpenGLWidget):
    """Simple orbit camera wireframe / solid renderer for parsed OBJ meshes."""

    def __init__(self, parent=None):
        if not _GL_AVAILABLE:
            raise RuntimeError("OpenGL is not available on this system")
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSamples(4)
        fmt.setDepthBufferSize(24)
        self.setFormat(fmt)
        self._verts: Optional[np.ndarray] = None
        self._normals: Optional[np.ndarray] = None
        self._tris: Optional[np.ndarray] = None
        self._edges: Optional[np.ndarray] = None
        self._center = np.zeros(3, dtype=np.float32)
        self._radius = 1.0
        self._yaw = -0.6
        self._pitch = 0.4
        self._distance = 3.0
        self._target_distance = 3.0
        self._dragging = False
        self._last_pos = (0, 0)
        self._wireframe = False
        self._gl: Optional[QOpenGLFunctions_3_3_Core] = None
        self._program: Optional[QOpenGLShaderProgram] = None
        self._vao: Optional[QOpenGLVertexArrayObject] = None
        self._vbo: Optional[QOpenGLBuffer] = None
        self._vbo_edges: Optional[QOpenGLBuffer] = None
        self._ebo_tris: Optional[QOpenGLBuffer] = None
        self._ebo_edges: Optional[QOpenGLBuffer] = None
        self._solid_color = QColor("#e88b3a")
        self._edge_color = QColor("#1b1c22")
        self._dirty = True

    def set_mesh(self, verts: np.ndarray, normals: np.ndarray, tris: np.ndarray, edges: np.ndarray) -> None:
        self._verts = np.ascontiguousarray(verts, dtype=np.float32)
        self._normals = np.ascontiguousarray(normals, dtype=np.float32)
        self._tris = np.ascontiguousarray(tris, dtype=np.uint32)
        self._edges = np.ascontiguousarray(edges, dtype=np.uint32)
        center = (self._verts.min(axis=0) + self._verts.max(axis=0)) / 2.0
        radius = float(np.linalg.norm(self._verts - center, axis=1).max())
        self._center = center.astype(np.float32)
        self._radius = max(radius, 1e-6)
        self._target_distance = self._radius * 2.6
        self._dirty = True
        self.reset_view()

    def set_wireframe(self, enabled: bool) -> None:
        self._wireframe = enabled
        self.update()

    def reset_view(self) -> None:
        self._yaw = -0.6
        self._pitch = 0.4
        self._distance = self._target_distance
        self.update()

    def initializeGL(self) -> None:
        self._gl = QOpenGLFunctions_3_3_Core(self)
        self._gl.initializeOpenGLFunctions()
        self._gl.glEnable(self._gl.GL_DEPTH_TEST)
        self._gl.glEnable(self._gl.GL_MULTISAMPLE)
        self._program = QOpenGLShaderProgram(self)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SRC)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SRC)
        self._program.link()
        self._build_buffers()

    def _build_buffers(self) -> None:
        if self._verts is None or self._program is None:
            return
        self._vao = QOpenGLVertexArrayObject(self)
        self._vao.create()
        self._vao.bind()
        self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vbo.create()
        self._vbo.bind()
        stride = 6 * 4
        interleaved = np.hstack([self._verts, self._normals]).astype(np.float32)
        self._vbo.allocate(interleaved.tobytes(), interleaved.nbytes)
        pos_loc = self._program.attributeLocation("aPos")
        normal_loc = self._program.attributeLocation("aNormal")
        self._gl.glEnableVertexAttribArray(pos_loc)
        self._gl.glVertexAttribPointer(pos_loc, 3, self._gl.GL_FLOAT, False, stride, 0)
        self._gl.glEnableVertexAttribArray(normal_loc)
        self._gl.glVertexAttribPointer(normal_loc, 3, self._gl.GL_FLOAT, False, stride, 3 * 4)

        self._ebo_tris = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        self._ebo_tris.create()
        self._ebo_tris.bind()
        self._ebo_tris.allocate(self._tris.tobytes(), self._tris.nbytes)

        if len(self._edges):
            self._vbo_edges = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo_edges.create()
            self._vbo_edges.bind()
            edge_verts = np.ascontiguousarray(self._verts[self._edges.ravel()], dtype=np.float32)
            self._vbo_edges.allocate(edge_verts.tobytes(), edge_verts.nbytes)
        self._vao.release()

    def paintGL(self) -> None:
        if self._gl is None or self._program is None or self._verts is None:
            return
        self._gl.glClearColor(0.082, 0.086, 0.106, 1.0)
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT | self._gl.GL_DEPTH_BUFFER_BIT)
        if self._dirty and self._vao is None:
            self._build_buffers()
            self._dirty = False
        elif self._dirty:
            self._build_buffers()
            self._dirty = False
        self._vao.bind()
        aspect = self.width() / max(self.height(), 1)
        proj = QMatrix4x4()
        proj.perspective(45.0, aspect, 0.01, 1000.0)
        eye = QMatrix4x4()
        eye.translate(0, 0, -self._distance)
        eye.rotate(self._pitch * 180.0 / math.pi, 1, 0, 0)
        eye.rotate(self._yaw * 180.0 / math.pi, 0, 1, 0)
        eye.translate(-self._center[0], -self._center[1], -self._center[2])
        mvp = proj * eye
        self._program.bind()
        self._program.setUniformValue("uMvp", mvp)
        self._program.setUniformValue("uModelView", eye)
        self._program.setUniformValue("uColor", self._solid_color)
        self._program.setUniformValue("uWireframe", 0.0)

        self._ebo_tris.bind()
        self._gl.glDrawElements(self._gl.GL_TRIANGLES, self._tris.size, self._gl.GL_UNSIGNED_INT, 0)
        self._ebo_tris.release()

        if self._vbo_edges is not None and self._vbo_edges.isCreated():
            self._vbo_edges.bind()
            self._gl.glEnableVertexAttribArray(0)
            self._gl.glVertexAttribPointer(0, 3, self._gl.GL_FLOAT, False, 3 * 4, 0)
            self._program.setUniformValue("uColor", self._edge_color)
            self._program.setUniformValue("uWireframe", 1.0)
            self._gl.glDrawArrays(self._gl.GL_LINES, 0, self._edges.size)
            self._vbo_edges.release()
        self._program.release()
        self._vao.release()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_pos = (event.position().x(), event.position().y())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            return
        x, y = event.position().x(), event.position().y()
        dx, dy = x - self._last_pos[0], y - self._last_pos[1]
        self._last_pos = (x, y)
        self._yaw -= dx * 0.01
        self._pitch += dy * 0.01
        self._pitch = max(-1.55, min(1.55, self._pitch))
        self.update()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._distance = max(self._radius * 0.3, min(self._radius * 20.0, self._distance / factor))
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        self.reset_view()

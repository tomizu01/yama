"""ウィンドウサイズと論理解像度を分離する表示ヘルパ。

`pygame.SCALED` を使うとウィンドウの最小サイズが論理解像度に固定されるため、
ユーザーがそれより小さくできない。本モジュールは

  1. ゲームは常に SCREEN_W × SCREEN_H の論理 Surface (`canvas`) に描画
  2. `present()` で実ウィンドウサイズへ smoothscale-blit
  3. マウス座標は実→論理を `to_logical()` で変換

という構造で、ユーザーが角ドラッグでウィンドウを自由にリサイズできるようにする。
"""

from __future__ import annotations

import pygame

from game import config as C


class _Display:
    def __init__(self) -> None:
        self.window = pygame.display.set_mode(
            (C.SCREEN_W, C.SCREEN_H), pygame.RESIZABLE
        )
        self.canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H)).convert()

    @property
    def surface(self) -> pygame.Surface:
        """ゲームロジックの描画先（常に論理サイズ）。"""
        return self.canvas

    def present(self) -> None:
        ws = self.window.get_size()
        if ws == (C.SCREEN_W, C.SCREEN_H):
            self.window.blit(self.canvas, (0, 0))
        else:
            scaled = pygame.transform.smoothscale(self.canvas, ws)
            self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def to_logical(self, pos: tuple[int, int]) -> tuple[float, float]:
        wx, wy = self.window.get_size()
        return (pos[0] * C.SCREEN_W / wx, pos[1] * C.SCREEN_H / wy)

    def mouse_pos(self) -> tuple[float, float]:
        return self.to_logical(pygame.mouse.get_pos())


_instance: _Display | None = None


def init() -> _Display:
    global _instance
    _instance = _Display()
    return _instance


def get() -> _Display:
    assert _instance is not None, "display.init() を先に呼ぶこと"
    return _instance


# --- 関数経由のショートカット（呼び出し側で .get() を書く手間を省く） ---

def surface() -> pygame.Surface:
    return get().surface


def present() -> None:
    get().present()


def mouse_pos() -> tuple[float, float]:
    return get().mouse_pos()


def to_logical(pos: tuple[int, int]) -> tuple[float, float]:
    return get().to_logical(pos)

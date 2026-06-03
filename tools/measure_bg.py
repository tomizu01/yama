"""bg.png の道路形状を測定する開発用スクリプト。"""
import pygame

pygame.init()
surf = pygame.image.load(r"C:\yama\sozai\images\bg.png")
w, h = surf.get_size()
print("size:", w, h)

for row in (h - 1, h - 10, 900, 800, 700, 650, 610):
    segs = []
    prev = None
    start = 0
    for x in range(w):
        c = surf.get_at((x, row))[:3]
        if c != prev:
            if prev is not None:
                segs.append((start, x - 1, prev))
            prev = c
            start = x
    segs.append((start, w - 1, prev))
    big = [s for s in segs if s[1] - s[0] >= 4]
    print(f"row {row}: " + " | ".join(f"{a}-{b} {c}" for a, b, c in big))

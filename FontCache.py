import pygame


class FontCache:
    """Fonts are rebuilt on resize, so keep one per pixel size."""

    def __init__(self):
        self._fonts = {}

    def get(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont(
                'consolas,dejavusansmono,couriernew,monospace', size, bold=bold
            )
        return self._fonts[key]

    def render_to_fit(self, text, color, max_width, size):
        """Render `text`, stepping the font down until it fits `max_width`."""
        while size > 7:
            surf = self.get(size).render(text, True, color)
            if surf.get_width() <= max_width:
                return surf
            size -= 1
        return self.get(size).render(text, True, color)

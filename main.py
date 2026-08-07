"""Stellar Wanderer — window bootstrap.

Opens a resizable pygame window and runs the main loop. Put drawing code in
`draw()`; it is called once per frame with the surface to paint on.
"""

import pygame

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1280, 720)
BACKGROUND = (8, 10, 24)  # deep space blue
FPS = 60


def draw(surface):
    """Render one frame. Graphics go here."""
    surface.fill(BACKGROUND)


def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == '__main__':
    print('Before main()')
    main()
    print('After main()')

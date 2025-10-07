import pygame
import sys
import math

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
GRASS_COLOR = (34, 139, 34)
PLAYER_COLOR = (65, 105, 225)  # Royal Blue
ENEMY_COLOR = (220, 20, 60)   # Crimson Red
ATTACK_RANGE_COLOR = (255, 255, 0, 100) # Yellow, semi-transparent
BULLET_COLOR = (255, 215, 0)   # Gold

# Player settings
PLAYER_RADIUS = 15
PLAYER_SPEED = 5
PLAYER_ATTACK_RANGE = 100
PLAYER_SHOOT_COOLDOWN = 300  # Milliseconds between shots

# Enemy settings
ENEMY_SIZE = 30
ENEMY_SPEED = 2

# Bullet settings
BULLET_RADIUS = 5
BULLET_SPEED = 10


# --- Game Classes ---

class Player:
    """Represents the player-controlled ball."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = PLAYER_RADIUS
        self.color = PLAYER_COLOR
        self.speed = PLAYER_SPEED
        self.last_shot_time = 0

    def move(self):
        """Move the player based on keyboard input."""
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= self.speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += self.speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= self.speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += self.speed

        # Normalize diagonal movement to prevent faster speed
        if dx != 0 and dy != 0:
            dx /= math.sqrt(2)
            dy /= math.sqrt(2)

        # Update position and keep player within screen bounds
        self.x = max(self.radius, min(SCREEN_WIDTH - self.radius, self.x + dx))
        self.y = max(self.radius, min(SCREEN_HEIGHT - self.radius, self.y + dy))

    def shoot(self, enemies, bullets):
        """Automatically shoots at the nearest enemy if in range and cooldown has passed."""
        current_time = pygame.time.get_ticks()
        if not enemies or current_time - self.last_shot_time < PLAYER_SHOOT_COOLDOWN:
            return # No enemies to shoot or shot is on cooldown

        # Find the nearest enemy
        closest_enemy = min(
            enemies,
            key=lambda e: math.hypot(e.rect.centerx - self.x, e.rect.centery - self.y)
        )

        distance = math.hypot(closest_enemy.rect.centerx - self.x, closest_enemy.rect.centery - self.y)

        # If the closest enemy is in range, create a bullet
        if distance <= PLAYER_ATTACK_RANGE:
            # Calculate direction for the bullet
            dx = closest_enemy.rect.centerx - self.x
            dy = closest_enemy.rect.centery - self.y
            
            bullets.append(Bullet(self.x, self.y, dx, dy))
            self.last_shot_time = current_time
            # print("Bullet fired!") # Console feedback for shooting

    def draw(self, screen):
        """Draws the player and its attack range indicator."""
        # Draw attack range (a semi-transparent circle)
        range_surface = pygame.Surface((PLAYER_ATTACK_RANGE * 2, PLAYER_ATTACK_RANGE * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surface, ATTACK_RANGE_COLOR, (PLAYER_ATTACK_RANGE, PLAYER_ATTACK_RANGE), PLAYER_ATTACK_RANGE)
        screen.blit(range_surface, (self.x - PLAYER_ATTACK_RANGE, self.y - PLAYER_ATTACK_RANGE))

        # Draw player
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

class Enemy:
    """Represents a square enemy that chases the player."""
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, ENEMY_SIZE, ENEMY_SIZE)
        self.color = ENEMY_COLOR
        self.speed = ENEMY_SPEED

    def move(self, player):
        """Moves the enemy towards the player."""
        dx = player.x - self.rect.centerx
        dy = player.y - self.rect.centery
        distance = math.hypot(dx, dy)

        # Normalize the vector and move
        if distance > 0:
            self.rect.x += (dx / distance) * self.speed
            self.rect.y += (dy / distance) * self.speed

    def draw(self, screen):
        """Draws the enemy on the screen."""
        pygame.draw.rect(screen, self.color, self.rect)

class Bullet:
    """Represents a projectile fired by the player."""
    def __init__(self, x, y, target_dx, target_dy):
        self.x = x
        self.y = y
        self.radius = BULLET_RADIUS
        self.color = BULLET_COLOR
        self.speed = BULLET_SPEED

        # Normalize direction vector
        distance = math.hypot(target_dx, target_dy)
        if distance > 0:
            self.dx = (target_dx / distance) * self.speed
            self.dy = (target_dy / distance) * self.speed
        else:
            self.dx, self.dy = 0, 0 # Should not happen if target exists

    def move(self):
        """Moves the bullet."""
        self.x += self.dx
        self.y += self.dy

    def draw(self, screen):
        """Draws the bullet on the screen."""
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def is_offscreen(self):
        """Checks if the bullet has moved off the screen."""
        return not (0 - self.radius < self.x < SCREEN_WIDTH + self.radius and
                    0 - self.radius < self.y < SCREEN_HEIGHT + self.radius)


# --- Main Game Setup ---
def main():
    """The main game loop and setup function."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Ball vs. Squares")
    clock = pygame.time.Clock()

    # Create game objects
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    enemies = [
        Enemy(100, 100),
        Enemy(700, 100),
        Enemy(100, 500),
        Enemy(700, 500),
        Enemy(400, 50)
    ]
    bullets = [] # List to hold active bullets

    running = True
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # --- Game Logic ---
        player.move()
        player.shoot(enemies, bullets) # Player now automatically shoots

        # Update and move enemies
        for enemy in enemies:
            enemy.move(player)
            # Check for collision with player
            if enemy.rect.colliderect(
                pygame.Rect(
                    player.x - player.radius,
                    player.y - player.radius,
                    player.radius * 2,
                    player.radius * 2
                )
            ):
                print("Game Over!")
                running = False
        
        # Update and move bullets
        for bullet in bullets[:]: # Iterate over a copy to allow modification
            bullet.move()
            if bullet.is_offscreen():
                bullets.remove(bullet)
                continue

            # Check for bullet collision with enemies
            for enemy in enemies[:]: # Iterate over a copy
                bullet_rect = pygame.Rect(bullet.x - bullet.radius, bullet.y - bullet.radius,
                                          bullet.radius * 2, bullet.radius * 2)
                if bullet_rect.colliderect(enemy.rect):
                    enemies.remove(enemy)
                    bullets.remove(bullet)
                    print("Enemy defeated!")
                    break # Bullet can only hit one enemy

        if not enemies:
            print("You Win!")
            running = False

        # --- Drawing ---
        screen.fill(GRASS_COLOR)  # Grassy field background
        player.draw(screen)
        for enemy in enemies:
            enemy.draw(screen)
        for bullet in bullets:
            bullet.draw(screen)

        pygame.display.flip()

        # --- Control Framerate ---
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
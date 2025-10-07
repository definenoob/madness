import pygame
import sys
import math
import random

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
GRASS_COLOR = (34, 139, 34)
PLAYER_COLOR = (65, 105, 225)
ENEMY_COLOR = (220, 20, 60)
BULLET_COLOR = (255, 215, 0)
HEALTH_BAR_BG = (139, 0, 0) # Dark Red
HEALTH_BAR_FG = (0, 255, 0) # Green
TEXT_COLOR = (255, 255, 255)
ITEM_COLORS = {
    'speed': (0, 191, 255),    # Deep Sky Blue
    'range': (255, 255, 0),    # Yellow
    'damage': (255, 69, 0)     # Orange Red
}

# --- Game Settings ---
# Player
PLAYER_RADIUS = 15
PLAYER_START_SPEED = 4.0
PLAYER_START_ATTACK_RANGE = 100
PLAYER_START_DAMAGE = 1
PLAYER_SHOOT_COOLDOWN = 300

# Enemy
ENEMY_SIZE = 30
ENEMY_START_SPEED = 1.5
ENEMY_START_HEALTH = 3

# Bullet
BULLET_RADIUS = 5
BULLET_SPEED = 10

# Spawning
INITIAL_SPAWN_COOLDOWN = 2000 # Milliseconds
MIN_SPAWN_COOLDOWN = 250
SPAWN_COOLDOWN_REDUCTION = 20 # Reduces per kill

# Item
ITEM_RADIUS = 10
ITEM_DROP_MILESTONE = 5

# --- Game Classes ---

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = PLAYER_RADIUS
        self.color = PLAYER_COLOR
        # Upgradable stats
        self.speed = PLAYER_START_SPEED
        self.attack_range = PLAYER_START_ATTACK_RANGE
        self.damage = PLAYER_START_DAMAGE
        
        self.last_shot_time = 0
        self.kills = 0

    def move(self):
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += 1

        if dx != 0 and dy != 0:
            dx /= math.sqrt(2)
            dy /= math.sqrt(2)

        self.x += dx * self.speed
        self.y += dy * self.speed
        self.x = max(self.radius, min(SCREEN_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(SCREEN_HEIGHT - self.radius, self.y))

    def shoot(self, enemies, bullets):
        current_time = pygame.time.get_ticks()
        if not enemies or current_time - self.last_shot_time < PLAYER_SHOOT_COOLDOWN:
            return

        closest_enemy = min(enemies, key=lambda e: math.hypot(e.rect.centerx - self.x, e.rect.centery - self.y))
        distance = math.hypot(closest_enemy.rect.centerx - self.x, closest_enemy.rect.centery - self.y)

        if distance <= self.attack_range:
            dx = closest_enemy.rect.centerx - self.x
            dy = closest_enemy.rect.centery - self.y
            bullets.append(Bullet(self.x, self.y, dx, dy, self.damage))
            self.last_shot_time = current_time

    def draw(self, screen):
        # Draw attack range aura
        range_surface = pygame.Surface((self.attack_range * 2, self.attack_range * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surface, (255, 255, 0, 70), (self.attack_range, self.attack_range), self.attack_range)
        screen.blit(range_surface, (self.x - self.attack_range, self.y - self.attack_range))
        # Draw player
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def collect_item(self, item):
        if item.type == 'speed':
            self.speed += 0.5
        elif item.type == 'range':
            self.attack_range += 15
        elif item.type == 'damage':
            self.damage += 1
        print(f"Collected {item.type}! Speed:{self.speed:.1f} Range:{self.attack_range} Damage:{self.damage}")

class Enemy:
    def __init__(self, x, y, health):
        self.rect = pygame.Rect(x, y, ENEMY_SIZE, ENEMY_SIZE)
        self.color = ENEMY_COLOR
        self.speed = ENEMY_START_SPEED
        self.max_health = health
        self.health = health

    def move(self, player):
        dx = player.x - self.rect.centerx
        dy = player.y - self.rect.centery
        distance = math.hypot(dx, dy)
        if distance > 0:
            self.rect.x += (dx / distance) * self.speed
            self.rect.y += (dy / distance) * self.speed
    
    def take_damage(self, amount):
        self.health -= amount
        return self.health <= 0

    def draw(self, screen, font):
        # Draw enemy
        pygame.draw.rect(screen, self.color, self.rect)
        # Draw health bar
        if self.health < self.max_health:
            bar_width = ENEMY_SIZE
            bar_height = 5
            health_pct = self.health / self.max_health
            
            bg_rect = pygame.Rect(self.rect.x, self.rect.y - bar_height - 3, bar_width, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_BG, bg_rect)
            
            fg_rect = pygame.Rect(self.rect.x, self.rect.y - bar_height - 3, bar_width * health_pct, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_FG, fg_rect)
        
        # Draw health text
        health_text = font.render(f"{self.health}/{self.max_health}", True, TEXT_COLOR)
        screen.blit(health_text, (self.rect.centerx - health_text.get_width() // 2, self.rect.y - 25))

class Bullet:
    def __init__(self, x, y, target_dx, target_dy, damage):
        self.x = x
        self.y = y
        self.radius = BULLET_RADIUS
        self.color = BULLET_COLOR
        self.speed = BULLET_SPEED
        self.damage = damage

        distance = math.hypot(target_dx, target_dy)
        if distance > 0:
            self.dx = (target_dx / distance) * self.speed
            self.dy = (target_dy / distance) * self.speed
        else:
            self.dx, self.dy = 0, 0

    def move(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def is_offscreen(self):
        return not (0 < self.x < SCREEN_WIDTH and 0 < self.y < SCREEN_HEIGHT)

class Item:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = ITEM_RADIUS
        self.type = random.choice(['speed', 'range', 'damage'])
        self.color = ITEM_COLORS[self.type]
        self.rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

    def draw(self, screen, font):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.radius)
        # Draw a letter to indicate type
        type_letter = self.type[0].upper()
        letter_surf = font.render(type_letter, True, (0,0,0))
        screen.blit(letter_surf, (self.x - letter_surf.get_width()//2, self.y - letter_surf.get_height()//2))

# --- Helper Functions ---
def spawn_enemy(player_kills):
    """Spawns an enemy off-screen."""
    side = random.choice(['top', 'bottom', 'left', 'right'])
    if side == 'top':
        x, y = random.randint(0, SCREEN_WIDTH), -ENEMY_SIZE
    elif side == 'bottom':
        x, y = random.randint(0, SCREEN_WIDTH), SCREEN_HEIGHT + ENEMY_SIZE
    elif side == 'left':
        x, y = -ENEMY_SIZE, random.randint(0, SCREEN_HEIGHT)
    else: # right
        x, y = SCREEN_WIDTH + ENEMY_SIZE, random.randint(0, SCREEN_HEIGHT)
    
    # Enemies get tougher as the game progresses
    health = ENEMY_START_HEALTH + (player_kills // 15)
    return Enemy(x, y, health)

def draw_ui(screen, player, font):
    """Draws game information like score and player stats."""
    score_text = font.render(f"Kills: {player.kills}", True, TEXT_COLOR)
    screen.blit(score_text, (10, 10))
    
    stats_text_speed = font.render(f"Speed: {player.speed:.1f}", True, ITEM_COLORS['speed'])
    screen.blit(stats_text_speed, (10, 35))
    
    stats_text_range = font.render(f"Range: {player.attack_range}", True, ITEM_COLORS['range'])
    screen.blit(stats_text_range, (10, 55))
    
    stats_text_damage = font.render(f"Damage: {player.damage}", True, ITEM_COLORS['damage'])
    screen.blit(stats_text_damage, (10, 75))

def draw_game_over(screen, score, font, big_font):
    """Draws the game over screen."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150)) # Semi-transparent black overlay
    screen.blit(overlay, (0, 0))
    
    title_text = big_font.render("Game Over", True, ENEMY_COLOR)
    screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, SCREEN_HEIGHT // 3))
    
    score_text = font.render(f"Final Score: {score}", True, TEXT_COLOR)
    screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2))
    
    restart_text = font.render("Press any key to restart", True, TEXT_COLOR)
    screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))


# --- Main Game Function ---
def game_loop():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Infinite Ball Survivor")
    clock = pygame.time.Clock()
    
    # Fonts
    ui_font = pygame.font.Font(None, 28)
    enemy_font = pygame.font.Font(None, 20)
    game_over_font = pygame.font.Font(None, 72)

    # Game state variables
    game_active = True
    
    # Game objects
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    enemies = []
    bullets = []
    items = []
    
    # Spawning timer
    last_spawn_time = pygame.time.get_ticks()
    spawn_cooldown = INITIAL_SPAWN_COOLDOWN

    # Main loop
    while True:
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if not game_active and event.type == pygame.KEYDOWN:
                return # Return to main menu to restart

        if game_active:
            # --- Spawning Logic ---
            if current_time - last_spawn_time > spawn_cooldown:
                enemies.append(spawn_enemy(player.kills))
                last_spawn_time = current_time
                # Increase difficulty
                spawn_cooldown = max(MIN_SPAWN_COOLDOWN, INITIAL_SPAWN_COOLDOWN - player.kills * SPAWN_COOLDOWN_REDUCTION)

            # --- Logic ---
            player.move()
            player.shoot(enemies, bullets)

            for enemy in enemies:
                enemy.move(player)
                if enemy.rect.colliderect(pygame.Rect(player.x - player.radius, player.y - player.radius, player.radius * 2, player.radius * 2)):
                    game_active = False # Player dies

            for item in items[:]:
                if item.rect.collidepoint(player.x, player.y):
                    player.collect_item(item)
                    items.remove(item)

            for bullet in bullets[:]:
                bullet.move()
                if bullet.is_offscreen():
                    bullets.remove(bullet)
                    continue
                
                for enemy in enemies[:]:
                    if enemy.rect.collidepoint(bullet.x, bullet.y):
                        if enemy.take_damage(bullet.damage):
                            player.kills += 1
                            # Check for item drop
                            if player.kills % ITEM_DROP_MILESTONE == 0:
                                items.append(Item(enemy.rect.centerx, enemy.rect.centery))
                            enemies.remove(enemy)
                        
                        if bullet in bullets: bullets.remove(bullet)
                        break

            # --- Drawing ---
            screen.fill(GRASS_COLOR)
            for item in items: item.draw(screen, ui_font)
            player.draw(screen)
            for enemy in enemies: enemy.draw(screen, enemy_font)
            for bullet in bullets: bullet.draw(screen)
            draw_ui(screen, player, ui_font)
        
        else: # Game is not active
            draw_game_over(screen, player.kills, ui_font, game_over_font)

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    while True:
        game_loop()
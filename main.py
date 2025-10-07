import pygame
import sys
import math
import numpy as np

# --- Constants ---
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 800
FPS = 60

# --- Colors ---
BACKGROUND_COLOR = (20, 20, 30) # Dark Navy/Space
PLAYER_COLOR = (0, 200, 255) # Cyan
BULLET_COLOR = (255, 255, 150) # Pale Yellow
TEXT_COLOR = (240, 240, 240)
# Auras
ATTACK_AURA_COLOR = (0, 200, 255, 30) # Cyan Aura
ITEM_AURA_COLOR = (255, 255, 255, 50)
# Enemies
SQUARE_COLOR = (255, 80, 80) # Soft Red
TRIANGLE_COLOR = (180, 80, 255) # Lavender
RIVAL_COLOR = (255, 165, 0) # Orange
RIVAL_BULLET_COLOR = (255, 50, 255) # Magenta
DIAMOND_COLOR = (0, 255, 200) # Bright Teal/Cyan (Bomb Immune)

# Health Bar
HEALTH_BAR_BG = (50, 50, 50)
HEALTH_BAR_FG = (80, 255, 80)
# Items
BOMB_COLOR = (220, 20, 60) # Crimson
ITEM_COLORS = {
    'speed': (0, 191, 255),
    'range': (255, 215, 0),
    'damage': (255, 69, 0),
    'bomb': BOMB_COLOR,
    'multishot': (200, 100, 255) # NEW: Color for Multishot item
}


# --- Game Settings ---
PLAYER_RADIUS = 12
PLAYER_START_SPEED = 4.0
PLAYER_START_ATTACK_RANGE = 250
PLAYER_ITEM_DROP_RANGE = 100
PLAYER_START_DAMAGE = 1
PLAYER_SHOOT_COOLDOWN = 300
SQUARE_START_HEALTH = 3
SQUARE_SPEED = 2.5 # Base speed for squares
TRIANGLE_START_HEALTH = 2
TRIANGLE_START_SPEED = 2.0
TRIANGLE_SPAWN_THRESHOLD = 10
# --- RIVAL SETTINGS ---
RIVAL_SPAWN_THRESHOLD = 0
RIVAL_START_HEALTH = 4
RIVAL_HEALTH_SCALING = 1
RIVAL_SPEED = 4.0
RIVAL_ATTACK_RANGE = 250
RIVAL_SHOOT_COOLDOWN = 1500
RIVAL_BULLET_SPEED = 7
# --- DIAMOND SETTINGS ---
DIAMOND_SPAWN_THRESHOLD_RIVALS = 2
DIAMOND_START_HEALTH = 5
DIAMOND_SPEED = 1.8
# -------------------------------------------
BULLET_RADIUS = 4
BULLET_SPEED = 12
INITIAL_SPAWN_COOLDOWN = 2000
MIN_SPAWN_COOLDOWN = 250
SPAWN_COOLDOWN_REDUCTION_PER_KILL = 20
ITEM_RADIUS = 9

# --- AI Settings ---
SEPARATION_FORCE = 0.5
SEPARATION_RADIUS = 40
# Square Evasion (NEW)
SQUARE_EVASION_RADIUS = 150  # How far away squares detect bullets
SQUARE_EVASION_FORCE = 0.0   # How strongly they push away from the bullet path
# Rival Strategy
RIVAL_OPTIMAL_FIRING_DISTANCE = 160
RIVAL_ENEMY_AVOIDANCE_RADIUS = 50
RIVAL_AVOIDANCE_FORCE = 1.5

# --- Helper Functions ---

def normalize_vector(vx, vy):
    magnitude = math.hypot(vx, vy)
    if magnitude == 0:
        return 0, 0
    return vx / magnitude, vy / magnitude

def predict_target_position(shooter_x, shooter_y, target_x, target_y, target_vx, target_vy, bullet_speed):
    # Advanced Predictive Aiming: Solves the quadratic equation for interception time.
    dx = target_x - shooter_x
    dy = target_y - shooter_y

    if bullet_speed <= 0:
        return target_x, target_y

    # Coefficients (a*t^2 + b*t + c = 0)
    a = target_vx**2 + target_vy**2 - bullet_speed**2
    b = 2 * (dx * target_vx + dy * target_vy)
    c = dx**2 + dy**2

    # If 'a' is near zero, speeds are similar; fallback to direct aiming.
    if abs(a) < 1e-6:
        if bullet_speed > 0:
            time_to_impact = math.hypot(dx, dy) / bullet_speed
        else:
            time_to_impact = 0
    else:
        # Discriminant (b^2 - 4ac)
        discriminant = b**2 - 4*a*c

        if discriminant < 0:
            # No real solution, fallback
            if bullet_speed > 0:
                time_to_impact = math.hypot(dx, dy) / bullet_speed
            else:
                time_to_impact = 0
        else:
            # Solutions for t
            t1 = (-b + math.sqrt(discriminant)) / (2*a)
            t2 = (-b - math.sqrt(discriminant)) / (2*a)

            # Choose the smallest positive time
            if t1 > 0 and (t2 < 0 or t1 < t2):
                time_to_impact = t1
            elif t2 > 0:
                time_to_impact = t2
            else:
                # Solutions are negative, fallback
                if bullet_speed > 0:
                    time_to_impact = math.hypot(dx, dy) / bullet_speed
                else:
                    time_to_impact = 0

    # Predict future position
    predicted_x = target_x + target_vx * time_to_impact
    predicted_y = target_y + target_vy * time_to_impact

    return predicted_x, predicted_y


# --- Game Classes ---

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0 # Velocity tracking for AI prediction
        self.radius = PLAYER_RADIUS
        self.rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
        self.color = PLAYER_COLOR
        self.speed = PLAYER_START_SPEED
        self.attack_range = PLAYER_START_ATTACK_RANGE
        self.item_drop_range = PLAYER_ITEM_DROP_RANGE
        self.damage = PLAYER_START_DAMAGE
        self.last_shot_time = 0
        self.kills = 0
        self.multishot_level = 1 # NEW: Player starts with 1 bullet per shot

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

        # Calculate new velocity (crucial for the AI to predict the player's movement)
        self.vx = dx * self.speed
        self.vy = dy * self.speed

        # Update position
        self.x = max(self.radius, min(SCREEN_WIDTH - self.radius, self.x + self.vx))
        self.y = max(self.radius, min(SCREEN_HEIGHT - self.radius, self.y + self.vy))
        self.rect.center = (self.x, self.y)

    def shoot(self, enemies, bullets, shot_sound):
        current_time = pygame.time.get_ticks()
        if not enemies or current_time - self.last_shot_time < PLAYER_SHOOT_COOLDOWN:
            return
        
        # MODIFIED: Logic for multi-shot
        all_targets = enemies
        # Sort all potential targets by distance
        all_targets.sort(key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
        
        # Select the closest N targets based on multishot_level
        targets_to_shoot = all_targets[:self.multishot_level]
        
        shot_fired = False
        for target in targets_to_shoot:
            distance = math.hypot(target.x - self.x, target.y - self.y)
            if distance <= self.attack_range:
                predicted_x, predicted_y = predict_target_position(
                    self.x, self.y,
                    target.x, target.y,
                    target.vx, target.vy,
                    BULLET_SPEED
                )
                
                dx, dy = predicted_x - self.x, predicted_y - self.y
                bullets.append(Bullet(self.x, self.y, dx, dy, self.damage, BULLET_COLOR))
                shot_fired = True
                
        if shot_fired:
            self.last_shot_time = current_time
            # Play sound once per volley
            channel = pygame.mixer.find_channel(True)
            if channel:
                channel.play(shot_sound)

    def draw(self, screen):
        # Draw Attack Range Aura
        range_surface = pygame.Surface((self.attack_range * 2, self.attack_range * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surface, ATTACK_AURA_COLOR, (self.attack_range, self.attack_range), self.attack_range)
        screen.blit(range_surface, (self.x - self.attack_range, self.y - self.attack_range))
        
        # Draw Item Pickup Range (Thin line)
        item_range_surface = pygame.Surface((self.item_drop_range * 2, self.item_drop_range * 2), pygame.SRCALPHA)
        pygame.draw.circle(item_range_surface, ITEM_AURA_COLOR, (self.item_drop_range, self.item_drop_range), self.item_drop_range, 1)
        screen.blit(item_range_surface, (self.x - self.item_drop_range, self.y - self.item_drop_range))
        
        # Draw Player Circle
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        # Add a darker core for depth
        pygame.draw.circle(screen, (0,0,0), (int(self.x), int(self.y)), self.radius // 3)


    def collect_item(self, item):
        # Bomb collection is handled in the main game loop
        if item.type == 'speed': self.speed += 0.3
        elif item.type == 'range': self.attack_range += 10
        elif item.type == 'damage': self.damage += 1
        elif item.type == 'multishot':
            self.multishot_level += 1
            RivalCircle.multishot_level += 1 # MODIFIED: Also upgrade all rivals

class Bullet:
    def __init__(self, x, y, target_dx, target_dy, damage, color, speed=BULLET_SPEED):
        self.x, self.y = x, y
        self.radius, self.speed, self.damage, self.color = BULLET_RADIUS, speed, damage, color
        self.rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
        
        # Normalize the direction vector
        self.dx, self.dy = normalize_vector(target_dx, target_dy)
        self.dx *= self.speed
        self.dy *= self.speed
        
        self.trail = [(x, y)] # Initialize trail

    def move(self): 
        self.x += self.dx
        self.y += self.dy
        self.rect.center = (self.x, self.y)
        
        # Update trail for visuals
        self.trail.append((self.x, self.y))
        if len(self.trail) > 5: # Keep trail short
            self.trail.pop(0)
            
    def draw(self, screen):
        # Draw trail line
        if len(self.trail) > 1:
            # Fade the trail color slightly
            trail_color = (max(0, self.color[0]-50), max(0, self.color[1]-50), max(0, self.color[2]-50))
            pygame.draw.lines(screen, trail_color, False, self.trail, 1)
            
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
    def is_offscreen(self): return not (0 < self.x < SCREEN_WIDTH and 0 < self.y < SCREEN_HEIGHT)

class Item:
    def __init__(self, x, y, kill_count=0, item_type=None):
        self.x, self.y = x, y
        self.radius = ITEM_RADIUS

        if item_type:
            self.type = item_type
        else:
            # Deterministic item drops based on kill count modulo 3
            item_types = ['speed', 'range', 'damage']
            self.type = item_types[kill_count % 3]

        self.color = ITEM_COLORS.get(self.type, (255, 255, 255)) # Default white if unknown
        self.rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
        self.creation_time = pygame.time.get_ticks()

    # The font passed here is the specific, smaller item_font.
    def draw(self, screen, font):
        # Add a subtle pulsing effect
        time_elapsed = pygame.time.get_ticks() - self.creation_time
        # Reduced pulse magnitude slightly
        pulse = math.sin(time_elapsed * 0.005) * 1.5
        draw_radius = self.radius + pulse
        
        pygame.draw.circle(screen, self.color, (self.x, self.y), draw_radius)
        # Use the first letter of the type as an indicator.
        letter_surf = font.render(self.type[0].upper(), True, (0,0,0))
        # Center the text
        screen.blit(letter_surf, (self.x - letter_surf.get_width()//2, self.y - letter_surf.get_height()//2))

class Enemy:
    # Base class for all AI entities
    def __init__(self, x, y, size, speed, health, color):
        self.x, self.y = x, y
        self.size = size
        self.rect = pygame.Rect(x - size/2, y - size/2, size, size)
        self.speed, self.max_health, self.health, self.color = speed, health, health, color
        self.vx, self.vy = 0, 0 # Velocity tracking

    def apply_force(self, fx, fy):
        # Simplified physics: directly add force to velocity
        self.vx += fx
        self.vy += fy

        # Cap speed if necessary, allowing bursts for dynamic movement
        max_speed_burst = self.speed * 1.5
        if isinstance(self, RivalCircle):
            max_speed_burst = self.speed * 2.5 # Allow rivals faster bursts for dodging
        elif isinstance(self, SquareEnemy):
            max_speed_burst = self.speed * 2.0 # Allow squares faster bursts for evasion

        current_speed = math.hypot(self.vx, self.vy)
        if current_speed > max_speed_burst:
            scale = max_speed_burst / current_speed
            self.vx *= scale
            self.vy *= scale
            
    def update_position(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (self.x, self.y)
    
    # Standardized strategic movement logic (Default: Swarm behavior)
    # obstacles: A list of entities to avoid (e.g., other enemies for separation)
    # player_bullets: A list of player bullets (for evasion, used by some subclasses)
    def strategic_move(self, player, obstacles, player_bullets):
        # 1. Attraction (Move towards the player)
        attraction_dx = player.x - self.x
        attraction_dy = player.y - self.y
        attraction_vx, attraction_vy = normalize_vector(attraction_dx, attraction_dy)
        
        # 2. Separation (Avoid crowding obstacles)
        separation_fx, separation_fy = 0, 0
        
        # Filter out self if present in the obstacles list
        neighbors = [other for other in obstacles if other != self]
        
        for other in neighbors:
            distance = math.hypot(other.x - self.x, other.y - self.y)
            if distance < SEPARATION_RADIUS and distance > 0:
                # Force is stronger when closer
                force_magnitude = (1 - (distance / SEPARATION_RADIUS)) * SEPARATION_FORCE
                # Direction away from the neighbor
                dx = self.x - other.x
                dy = self.y - other.y
                sep_vx, sep_vy = normalize_vector(dx, dy)
                separation_fx += sep_vx * force_magnitude
                separation_fy += sep_vy * force_magnitude

        # Combine behaviors
        self.vx = attraction_vx * self.speed
        self.vy = attraction_vy * self.speed
        
        # Apply separation force
        self.apply_force(separation_fx, separation_fy)
        self.update_position()

        
    def take_damage(self, amount):
        self.health -= amount
        return self.health <= 0

    def draw_health_bar(self, screen, font):
        # Only draw health bar if damaged or if it's a high-health unit (to show scaling)
        is_high_health = (isinstance(self, RivalCircle) and self.max_health > RIVAL_START_HEALTH) or isinstance(self, DiamondEnemy)
        
        if self.health < self.max_health or is_high_health:
            bar_width, bar_height = self.size * 1.5, 4 # Wider bar for visibility
            health_pct = max(0, self.health / self.max_health)
            
            # Position above the entity
            bar_x = self.x - bar_width / 2
            bar_y = self.y - self.size / 2 - bar_height - 8
            
            bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_BG, bg_rect)
            
            fg_rect = pygame.Rect(bar_x, bar_y, bar_width * health_pct, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_FG, fg_rect)

    def on_death(self): return []
    
    # Default bomb handling (most enemies die)
    def handle_bomb(self):
        # Return True if the enemy should be destroyed by the bomb
        return True

class SquareEnemy(Enemy):
    def __init__(self, x, y, health):
        super().__init__(x, y, 25, SQUARE_SPEED, health, SQUARE_COLOR)
        
    # Override strategic move to include evasion
    def strategic_move(self, player, obstacles, player_bullets):
        # 1. Attraction (Move towards the player)
        attraction_dx = player.x - self.x
        attraction_dy = player.y - self.y
        attraction_vx, attraction_vy = normalize_vector(attraction_dx, attraction_dy)
        
        # 2. Separation (Avoid crowding other enemies)
        separation_fx, separation_fy = 0, 0
        neighbors = [other for other in obstacles if other != self]
        for other in neighbors:
            distance = math.hypot(other.x - self.x, other.y - self.y)
            if distance < SEPARATION_RADIUS and distance > 0:
                force_magnitude = (1 - (distance / SEPARATION_RADIUS)) * SEPARATION_FORCE
                dx = self.x - other.x
                dy = self.y - other.y
                sep_vx, sep_vy = normalize_vector(dx, dy)
                separation_fx += sep_vx * force_magnitude
                separation_fy += sep_vy * force_magnitude

        # 3. Evasion (Dodge player bullets)
        evasion_fx, evasion_fy = 0, 0
        closest_threat_distance = float('inf')

        for bullet in player_bullets:
            distance = math.hypot(bullet.x - self.x, bullet.y - self.y)
            
            if distance < SQUARE_EVASION_RADIUS:
                # Check if the bullet is moving towards the square.
                # Vector from enemy to bullet
                dx_eb = bullet.x - self.x
                dy_eb = bullet.y - self.y
                
                # Dot product of (vector from enemy to bullet) and (bullet velocity)
                # If negative, the angle between them is > 90 deg, meaning the bullet is generally approaching.
                dot_product = dx_eb * bullet.dx + dy_eb * bullet.dy
                
                if dot_product < 0:
                    # Bullet is a threat. Calculate evasion direction.
                    # We want to move perpendicular to the bullet's trajectory.
                    # Bullet trajectory (normalized):
                    b_vx, b_vy = normalize_vector(bullet.dx, bullet.dy)
                    
                    # Perpendicular vectors (left and right relative to bullet path)
                    # Deterministic choice: Always dodge "left" (-b_vy, b_vx) relative to the bullet's direction.
                    perp_vx, perp_vy = -b_vy, b_vx
                    
                    # The force magnitude depends on how close the threat is
                    if distance > 0:
                        force_magnitude = (1 - (distance / SQUARE_EVASION_RADIUS)) * SQUARE_EVASION_FORCE
                    else:
                        force_magnitude = SQUARE_EVASION_FORCE

                    # Prioritize the closest threat (only consider the most immediate danger)
                    if distance < closest_threat_distance:
                        evasion_fx = perp_vx * force_magnitude
                        evasion_fy = perp_vy * force_magnitude
                        closest_threat_distance = distance

        # Combine behaviors
        # If evading, prioritize evasion over attraction slightly
        if closest_threat_distance != float('inf'):
            attraction_weight = 0.5
        else:
            attraction_weight = 1.0

        self.vx = attraction_vx * self.speed * attraction_weight
        self.vy = attraction_vy * self.speed * attraction_weight
        
        # Apply separation and evasion forces
        self.apply_force(separation_fx + evasion_fx, separation_fy + evasion_fy)
        self.update_position()

    def draw(self, screen, font):
        # Rotate the square based on movement direction
        angle = math.degrees(math.atan2(self.vy, self.vx))
        # Use pygame.Surface for rotation to handle alpha/transparency correctly
        rotated_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.rect(rotated_surface, self.color, (0, 0, self.size, self.size))
        rotated_image = pygame.transform.rotate(rotated_surface, -angle)
        new_rect = rotated_image.get_rect(center = self.rect.center)
        screen.blit(rotated_image, new_rect.topleft)
        
        self.draw_health_bar(screen, font)

class TriangleEnemy(Enemy):
    def __init__(self, x, y, health, size):
        speed = TRIANGLE_START_SPEED * (1.5 if size < 30 else 1.0) # Smaller ones are faster
        super().__init__(x, y, size, speed, health, TRIANGLE_COLOR)
    
    # Uses the default Enemy.strategic_move (Swarm behavior, no evasion)

    def draw(self, screen, font):
        # Calculate points for an equilateral triangle
        height = self.size * (math.sqrt(3)/2)
        p1 = (0, -height / 2) # Top
        p2 = (-self.size / 2, height / 2) # Bottom left
        p3 = (self.size / 2, height / 2) # Bottom right
        
        # Rotate the triangle based on movement direction
        # Handle zero velocity case (point upwards)
        if self.vx == 0 and self.vy == 0:
            angle = -math.pi/2
        else:
            # Align the tip (p1) with the direction of movement
            angle = math.atan2(self.vy, self.vx) - math.pi/2

        def rotate_point(p, angle):
            x, y = p
            rx = x * math.cos(angle) - y * math.sin(angle)
            ry = x * math.sin(angle) + y * math.cos(angle)
            return (rx + self.x, ry + self.y)

        points = [rotate_point(p, angle) for p in [p1, p2, p3]]
        
        pygame.draw.polygon(screen, self.color, points)
        self.draw_health_bar(screen, font)
        
    def on_death(self):
        # Split into two smaller triangles if large enough
        if self.size >= 30:
            new_health = max(1, self.max_health // 2)
            new_size = self.size // 2
            # Spawn slightly offset (Deterministic positions)
            return [TriangleEnemy(self.x - 10, self.y, new_health, new_size),
                    TriangleEnemy(self.x + 10, self.y, new_health, new_size)]
        return []

class DiamondEnemy(Enemy):
    def __init__(self, x, y, health):
        # Size 30, Speed from constant
        super().__init__(x, y, 30, DIAMOND_SPEED, health, DIAMOND_COLOR)
        self.duplication_pending = False # Flag to indicate it needs to duplicate

    # Uses the default Enemy.strategic_move (Swarm behavior, no evasion)

    def draw(self, screen, font):
        # Calculate points for a diamond (rhombus)
        # Points relative to the center
        p1 = (0, -self.size / 2) # Top
        p2 = (self.size / 2, 0) # Right
        p3 = (0, self.size / 2) # Bottom
        p4 = (-self.size / 2, 0) # Left

        # Rotate the diamond based on movement direction
        if self.vx == 0 and self.vy == 0:
            angle = 0
        else:
            # Standard rotation based on velocity
            angle = math.atan2(self.vy, self.vx)

        def rotate_point(p, angle):
            x, y = p
            rx = x * math.cos(angle) - y * math.sin(angle)
            ry = x * math.sin(angle) + y * math.cos(angle)
            return (rx + self.x, ry + self.y)

        points = [rotate_point(p, angle) for p in [p1, p2, p3, p4]]

        pygame.draw.polygon(screen, self.color, points)
        # Draw a slightly darker inner diamond for visual appeal
        inner_points = [rotate_point((px*0.5, py*0.5), angle) for px, py in [p1, p2, p3, p4]]
        darker_color = tuple(max(0, c-80) for c in self.color)
        pygame.draw.polygon(screen, darker_color, inner_points)
        
        self.draw_health_bar(screen, font)

    def handle_bomb(self):
        # This method is called when a bomb explodes while the diamond is on screen.
        # Instead of taking damage, it flags itself for duplication.
        self.duplication_pending = True
        # Return False as it is not destroyed by the bomb
        return False

class RivalCircle(Enemy):
    # NEW: Class attribute to track multishot level for ALL rivals
    multishot_level = 1

    def __init__(self, x, y, health):
        super().__init__(x, y, 20, RIVAL_SPEED, health, RIVAL_COLOR)
        self.attack_range = RIVAL_ATTACK_RANGE
        self.last_shot_time = 0

    # Advanced strategic movement (Aggressive Player Hunt)
    # obstacles: Standard enemies the rival should avoid
    # player_bullets: Player bullets (Rivals currently do not dodge these, prioritizing kiting)
    def strategic_move(self, player, obstacles, player_bullets):
        
        # 1. Positioning relative to the player (Kiting/Strafing)
        distance_to_player = math.hypot(player.x - self.x, player.y - self.y)
            
        # Vector towards player
        px, py = normalize_vector(player.x - self.x, player.y - self.y)
            
        if distance_to_player > RIVAL_OPTIMAL_FIRING_DISTANCE:
            # Move closer
            move_x, move_y = px * self.speed, py * self.speed
        elif distance_to_player < RIVAL_OPTIMAL_FIRING_DISTANCE - 30:
            # Move away (Kiting)
            move_x, move_y = -px * self.speed, -py * self.speed
        else:
            # Strafe around the player (deterministic direction: clockwise)
            move_x, move_y = py * self.speed * 0.8, -px * self.speed * 0.8

        # 2. Obstacle Avoidance
        avoidance_fx, avoidance_fy = 0, 0

        # Check against standard enemies for avoidance
        for obstacle in obstacles:
            # Ensure we don't avoid ourselves (safety check)
            if obstacle == self: continue
            
            distance = math.hypot(obstacle.x - self.x, obstacle.y - self.y)
            if distance < RIVAL_ENEMY_AVOIDANCE_RADIUS and distance > 0:
                # Calculate avoidance force
                force_magnitude = (1 - (distance / RIVAL_ENEMY_AVOIDANCE_RADIUS)) * RIVAL_AVOIDANCE_FORCE
                # Direction away from the obstacle
                dx = self.x - obstacle.x
                dy = self.y - obstacle.y
                avoid_vx, avoid_vy = normalize_vector(dx, dy)
                avoidance_fx += avoid_vx * force_magnitude
                avoidance_fy += avoid_vy * force_magnitude

        # Combine Kiting movement with avoidance forces
        self.vx = move_x
        self.vy = move_y
        
        self.apply_force(avoidance_fx, avoidance_fy)
        self.update_position()

    def shoot(self, player, enemies, rival_bullets, shot_sound):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_shot_time < RIVAL_SHOOT_COOLDOWN:
            return
        
        # MODIFIED: Target selection now includes player AND standard enemies
        potential_targets = [player] + enemies
        
        # Sort all potential targets by distance to the rival
        potential_targets.sort(key=lambda t: math.hypot(t.x - self.x, t.y - self.y))
        
        # Select the closest N targets based on the CLASS multishot level
        targets_to_shoot = potential_targets[:RivalCircle.multishot_level]
        
        shot_fired = False
        for target in targets_to_shoot:
            distance = math.hypot(target.x - self.x, target.y - self.y)
            if distance <= self.attack_range:
                # Use predictive aiming against the target
                predicted_x, predicted_y = predict_target_position(
                    self.x, self.y,
                    target.x, target.y,
                    target.vx, target.vy,
                    RIVAL_BULLET_SPEED
                )
                
                dx = predicted_x - self.x
                dy = predicted_y - self.y
                
                rival_bullets.append(Bullet(self.x, self.y, dx, dy, 1, RIVAL_BULLET_COLOR, RIVAL_BULLET_SPEED))
                shot_fired = True

        if shot_fired:
            self.last_shot_time = current_time
            # Play sound once per volley
            channel = pygame.mixer.find_channel(True)
            if channel:
                channel.play(shot_sound)
    
    def draw(self, screen, font):
        # Draw Attack Range (very faint)
        range_surface = pygame.Surface((self.attack_range * 2, self.attack_range * 2), pygame.SRCALPHA)
        # Add alpha component to the color for the aura
        aura_color = self.color + (20,) if len(self.color) == 3 else self.color
        pygame.draw.circle(range_surface, aura_color, (self.attack_range, self.attack_range), self.attack_range)
        screen.blit(range_surface, (self.x - self.attack_range, self.y - self.attack_range))
        
        # Draw Rival Circle
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size // 2)
        self.draw_health_bar(screen, font)

# --- Audio Generation ---
# (Audio generation functions and initialization remain the same as they are robust and deterministic)

# Define robust initialization structure for audio
# Dummy classes provide fallback methods if audio initialization fails.
class DummySound:
    def play(self, *args, **kwargs): pass
    def stop(self, *args, **kwargs): pass
    def get_busy(self): return False

class DummyChannel:
    def play(self, *args, **kwargs): pass
    def stop(self, *args, **kwargs): pass
    def get_busy(self): return False
    # Crucial for dynamic music switching logic
    def get_sound(self): return None 

def generate_sound_array(frequency, duration, sample_rate=44100, amplitude=0.5, wave_type='sine'):
    # Ensure frequency is positive
    if frequency <= 0:
        frequency = 1e-6

    num_samples = int(sample_rate * duration)
    # Handle edge case of very short duration resulting in zero samples
    if num_samples == 0:
        return np.zeros(0, dtype=np.int16)
        
    time_array = np.linspace(0., duration, num_samples, endpoint=False)
    
    if wave_type == 'sine':
        wave = np.sin(2 * np.pi * frequency * time_array)
    elif wave_type == 'soft_square':
        # Approximation using Fourier series
        wave = np.sin(2 * np.pi * frequency * time_array)
        if frequency * 3 < sample_rate / 2:
            wave += (1/3) * np.sin(2 * np.pi * 3 * frequency * time_array)
        if frequency * 5 < sample_rate / 2:
            wave += (1/5) * np.sin(2 * np.pi * 5 * frequency * time_array)
    elif wave_type == 'noise':
        # Deterministic noise: frequency modulated sine wave
        mod_freq = 50
        mod_wave = np.sin(2 * np.pi * mod_freq * time_array)
        wave = np.sin(2 * np.pi * (frequency + mod_wave*20) * time_array)
    else:
        wave = np.sin(2 * np.pi * frequency * time_array)
        
    # Apply fade out (Envelope)
    fade_out = np.linspace(1., 0., num_samples)**1.5
    wave *= fade_out
    
    # Normalize and convert to 16-bit PCM
    max_abs = np.max(np.abs(wave))
    wave = wave / max_abs if max_abs > 0 else wave 
    sound_data = (wave * (2**15 - 1) * amplitude).astype(np.int16)
    return sound_data

def generate_explosion_sound(duration=0.5, start_freq=100, end_freq=50, amplitude=0.7):
    sample_rate=44100
    num_samples = int(sample_rate * duration)
    
    # Check if mixer is initialized
    if not pygame.mixer.get_init():
        return DummySound()

    # Handle zero samples case
    if num_samples == 0:
        return pygame.sndarray.make_sound(np.zeros((1, 2), dtype=np.int16))

    # Generate deterministic noise
    time_array = np.linspace(0., duration, num_samples, endpoint=False)
    frequency = np.linspace(start_freq, end_freq, num_samples)
    
    # Use frequency modulated noise for a deeper explosion sound
    mod_freq = 40
    mod_wave = np.sin(2 * np.pi * mod_freq * time_array)
    wave = np.sin(2 * np.pi * (frequency + mod_wave*30) * time_array)

    # Strong fade out
    fade_out = np.linspace(1., 0., num_samples)**3
    wave *= fade_out

    max_abs = np.max(np.abs(wave))
    wave = wave / max_abs if max_abs > 0 else wave 
    sound_data = (wave * (2**15 - 1) * amplitude).astype(np.int16)
    
    # Convert to stereo
    stereo_sound_data = np.ascontiguousarray(np.vstack((sound_data, sound_data)).T)
    return pygame.sndarray.make_sound(stereo_sound_data)


def generate_full_melody_sound(note_sequence, sample_rate=44100, amplitude=0.2, wave_type='sine'):
    # Generate arrays for each note
    melody_arrays = [generate_sound_array(freq, dur, sample_rate, amplitude, wave_type) for freq, dur in note_sequence]
    # Filter out empty arrays
    melody_arrays = [arr for arr in melody_arrays if arr.size > 0]

    # Check if mixer is initialized
    if not pygame.mixer.get_init():
        return DummySound()

    # Handle case where all arrays were empty
    if not melody_arrays:
        return pygame.sndarray.make_sound(np.zeros((1, 2), dtype=np.int16))

    # Concatenate into a single track
    full_melody_array = np.concatenate(melody_arrays)
    
    # Stereo sound (Melody slightly panned)
    left_channel = (full_melody_array * 0.8).astype(np.int16)
    right_channel = (full_melody_array * 0.5).astype(np.int16)
    
    stereo_melody_array = np.ascontiguousarray(np.vstack((left_channel, right_channel)).T)
    return pygame.sndarray.make_sound(stereo_melody_array)

def generate_bass_track(note_sequence, sample_rate=44100, amplitude=0.3, wave_type='soft_square'):
    bass_arrays = [generate_sound_array(freq, dur, sample_rate, amplitude, wave_type) for freq, dur in note_sequence]
    bass_arrays = [arr for arr in bass_arrays if arr.size > 0]

    # Check if mixer is initialized
    if not pygame.mixer.get_init():
        return DummySound()

    if not bass_arrays:
        return pygame.sndarray.make_sound(np.zeros((1, 2), dtype=np.int16))

    full_bass_array = np.concatenate(bass_arrays)
    
    # Stereo sound (Bass centered)
    stereo_bass_array = np.ascontiguousarray(np.vstack((full_bass_array, full_bass_array)).T)
    return pygame.sndarray.make_sound(stereo_bass_array)


def generate_laser_sound(duration=0.1, start_freq=600, end_freq=300):
    sample_rate=44100
    num_samples = int(sample_rate * duration)
    
    # Check if mixer is initialized
    if not pygame.mixer.get_init():
        return DummySound()

    if num_samples == 0:
        return pygame.sndarray.make_sound(np.zeros((1, 2), dtype=np.int16))

    # Ensure frequencies are positive
    start_freq = max(1e-6, start_freq)
    end_freq = max(1e-6, end_freq)

    # Frequency sweep
    frequency = np.linspace(start_freq, end_freq, num_samples)
    # Generate wave (Sine) - np.cumsum integrates the frequency over time for the phase sweep
    wave = np.sin(2 * np.pi * np.cumsum(frequency) / sample_rate)
    
    # Envelope (Fade out)
    fade = np.linspace(1., 0., num_samples)**2
    wave *= fade
    
    sound_data = (wave * (2**15 - 1) * 0.3).astype(np.int16)
    stereo_sound_data = np.ascontiguousarray(np.vstack((sound_data, sound_data)).T)
    return pygame.sndarray.make_sound(stereo_sound_data)

# --- Game Logic Functions ---

def spawn_entity(player_kills, total_entities_spawned, rivals_spawned_count):
    # Deterministic spawning locations
    spawn_sides = ['top', 'right', 'bottom', 'left']
    side = spawn_sides[total_entities_spawned % 4]
    
    # Use a pseudo-random but deterministic seed for positioning along the edge
    position_seed = (total_entities_spawned * 137) 
    
    if side == 'top':
        x, y = position_seed % SCREEN_WIDTH, -30
    elif side == 'bottom':
        x, y = position_seed % SCREEN_WIDTH, SCREEN_HEIGHT + 30
    elif side == 'left':
        x, y = -30, position_seed % SCREEN_HEIGHT
    else: # right
        x, y = SCREEN_WIDTH + 30, position_seed % SCREEN_HEIGHT
    
    # Deterministic enemy type selection based on progression and spawn count
    
    # Spawn a Diamond every 8 spawns if the rival threshold is met
    if rivals_spawned_count >= DIAMOND_SPAWN_THRESHOLD_RIVALS and (total_entities_spawned + 1) % 8 == 0:
        # Health scales slightly with kills
        health = DIAMOND_START_HEALTH + (player_kills // 20)
        return DiamondEnemy(x, y, health)
    
    # Spawn a Rival every 10 spawns after the kill threshold
    if player_kills >= RIVAL_SPAWN_THRESHOLD and (total_entities_spawned + 1) % 10 == 0:
        # Calculate progressive health based on how many rivals have already spawned
        health = RIVAL_START_HEALTH + (rivals_spawned_count * RIVAL_HEALTH_SCALING)
        return RivalCircle(x, y, health)
    
    # Spawn a Triangle every 5 spawns after the kill threshold
    elif player_kills >= TRIANGLE_SPAWN_THRESHOLD and (total_entities_spawned + 1) % 5 == 0:
        health = TRIANGLE_START_HEALTH + (player_kills // 12)
        return TriangleEnemy(x, y, health, 30) # Start with large size
    
    else:
        # Default spawn: Square (Now Evasive)
        health = SQUARE_START_HEALTH + (player_kills // 15)
        return SquareEnemy(x, y, health)

def calculate_intensity(spawn_cooldown):
    # Calculate intensity based on how close the current cooldown is to the minimum cooldown.
    range_of_cooldowns = INITIAL_SPAWN_COOLDOWN - MIN_SPAWN_COOLDOWN
    if range_of_cooldowns > 0:
        intensity = (INITIAL_SPAWN_COOLDOWN - spawn_cooldown) / range_of_cooldowns
    else:
        # If min equals initial, intensity is maximum
        intensity = 1.0
    # Clamp between 0.0 and 1.0
    return max(0.0, min(1.0, intensity))

def draw_ui(screen, player, font, spawn_cooldown, rivals_spawned_count):
    # Display Kills
    score_text = font.render(f"Kills: {player.kills}", True, TEXT_COLOR)
    screen.blit(score_text, (10, 10))
    
    # Display Stats
    stats_y = 40
    stats = [
        (f"Speed: {player.speed:.1f}", ITEM_COLORS['speed']),
        (f"Range: {player.attack_range}", ITEM_COLORS['range']),
        (f"Damage: {player.damage}", ITEM_COLORS['damage']),
        (f"Shots: {player.multishot_level}", ITEM_COLORS['multishot']) # NEW: Display multishot level
    ]
    for text, color in stats:
        surf = font.render(text, True, color)
        screen.blit(surf, (10, stats_y))
        stats_y += 25

    # Display Intensity indicator
    intensity = calculate_intensity(spawn_cooldown)
    intensity_text = font.render(f"Intensity: {intensity*100:.0f}%", True, TEXT_COLOR)
    screen.blit(intensity_text, (10, stats_y + 5))
    

def draw_game_over(screen, score, font, big_font):
    # Darken the screen with a semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    title = big_font.render("YOU WERE OVERWHELMED", True, SQUARE_COLOR)
    score_text = font.render(f"Final Kills: {score}", True, TEXT_COLOR)
    restart_text = font.render("Press R to restart", True, TEXT_COLOR)
    
    # Center the text elements
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 3))
    screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2))
    screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

def title_screen(screen, clock):
    # Initialize font module
    pygame.font.init()
    # Use system fonts if available, otherwise default
    try:
        # Prioritize specific stylistic fonts
        title_font = pygame.font.SysFont('Impact, Charcoal, sans-serif', 150)
        subtitle_font = pygame.font.SysFont('Verdana, Geneva, sans-serif', 36)
    except Exception:
        # Fallback to default pygame font
        title_font = pygame.font.Font(None, 150)
        subtitle_font = pygame.font.Font(None, 36)

    
    title_text = title_font.render("MADNESS", True, RIVAL_COLOR)
    subtitle_text = subtitle_font.render("Press any key to begin", True, TEXT_COLOR)
    
    # Background animation (Deterministic moving shapes)
    # Initialize a set of background squares with deterministic properties
    squares = []
    for i in range(10):
        x = (i * 80) % SCREEN_WIDTH
        y = (i * 60) % SCREEN_HEIGHT
        speed = 0.5 + (i % 3) * 0.5
        squares.append({'rect': pygame.Rect(x, y, 30, 30), 'speed': speed, 'angle': (i * 36)})

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                running = False

        screen.fill(BACKGROUND_COLOR)
        
        # Update and draw background animation
        for square in squares:
            # Movement based on angle and speed
            dx = math.cos(math.radians(square['angle'])) * square['speed']
            dy = math.sin(math.radians(square['angle'])) * square['speed']
            square['rect'].x += dx
            square['rect'].y += dy
            
            # Wrap around screen edges
            if square['rect'].right < 0: square['rect'].left = SCREEN_WIDTH
            if square['rect'].left > SCREEN_WIDTH: square['rect'].right = 0
            if square['rect'].bottom < 0: square['rect'].top = SCREEN_HEIGHT
            if square['rect'].top > SCREEN_HEIGHT: square['rect'].bottom = 0
            
            # Draw faint squares using a Surface with alpha
            s = pygame.Surface((30, 30), pygame.SRCALPHA)
            color_alpha = SQUARE_COLOR + (50,) if len(SQUARE_COLOR) == 3 else SQUARE_COLOR
            s.fill(color_alpha)
            screen.blit(s, square['rect'].topleft)

        # Draw Title
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, SCREEN_HEIGHT // 3))
        
        # Pulsing subtitle effect using time-based sine wave for alpha
        alpha = int(128 + 127 * math.sin(pygame.time.get_ticks() * 0.005))
        # Create a temporary surface to apply alpha blending
        temp_surface = pygame.Surface(subtitle_text.get_size(), pygame.SRCALPHA)
        temp_surface.blit(subtitle_text, (0,0))
        temp_surface.set_alpha(alpha)
        
        screen.blit(temp_surface, (SCREEN_WIDTH // 2 - subtitle_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

        pygame.display.flip()
        clock.tick(FPS)

# --- Main Game Function ---
def game_loop(screen, clock, audio_assets):
    
    # Fonts Initialization (Attempt system fonts, fallback to default)
    pygame.font.init()
    try:
        ui_font = pygame.font.SysFont('Verdana, Geneva, sans-serif', 24)
        enemy_font = pygame.font.SysFont('Verdana, Geneva, sans-serif', 16)
        # Smaller, bold font for items (size 14)
        item_font = pygame.font.SysFont('Verdana, Geneva, sans-serif', 14, bold=True) 
        go_font_big = pygame.font.SysFont('Impact, Charcoal, sans-serif', 72)
    except Exception:
        ui_font = pygame.font.Font(None, 28)
        enemy_font = pygame.font.Font(None, 18)
        item_font = pygame.font.Font(None, 16)
        go_font_big = pygame.font.Font(None, 72)


    # Unpack Audio Assets
    melody_tracks = audio_assets['melodies']
    bass_tracks = audio_assets['bass']
    rival_melody = audio_assets['rival_melody']
    rival_bass = audio_assets['rival_bass']
    
    shot_sound = audio_assets['shot']
    hit_sound = audio_assets['hit']
    death_sound = audio_assets['death']
    bomb_sound = audio_assets['bomb']
    # Specific channels reserved for music
    music_channel_melody = audio_assets['channel_melody']
    music_channel_bass = audio_assets['channel_bass']

    # Game state initialization
    game_active = True
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    # Reset the shared rival multishot level at the start of each game
    RivalCircle.multishot_level = 1
    
    # Separate lists: 'enemies' for standard types (including Diamonds), 'rivals' for RivalCircles
    enemies = []
    rivals = []
    bullets = [] # Player bullets
    rival_bullets = []
    items = []
    
    last_spawn_time = pygame.time.get_ticks()
    total_entities_spawned = 0
    rivals_spawned_count = 0 # Track total rivals spawned for difficulty scaling and Diamond spawning
    spawn_cooldown = INITIAL_SPAWN_COOLDOWN
    current_music_index = -1 # Track current intensity music index

    # Visual Effects (Screen Flash)
    flash_alpha = 0

    # Ensure music channels are clear before starting the game loop
    music_channel_melody.stop()
    music_channel_bass.stop()

    # --- Game Loop Start ---
    while True:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # This handles the ESC key
                    pygame.quit()
                    sys.exit()
            if not game_active:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        # Ensure music stops before restarting the function
                        music_channel_melody.stop()
                        music_channel_bass.stop()
                        return # Exit the function to restart the game loop

        # --- Dynamic Music Management (Intensity and Rivals) ---
        if game_active:
            is_rival_active = len(rivals) > 0
            
            if is_rival_active:
                # Rival active: Play the rival theme
                # Check if the current sound playing is not the rival melody
                if music_channel_melody.get_sound() != rival_melody:
                    music_channel_melody.play(rival_melody)
                    music_channel_bass.play(rival_bass)
                # Ensure it loops if the channel finished playing
                elif not music_channel_melody.get_busy():
                    music_channel_melody.play(rival_melody)
                    music_channel_bass.play(rival_bass)

            else:
                # No rivals: Use intensity-based music
                intensity = calculate_intensity(spawn_cooldown)
                num_tracks = len(melody_tracks)
                
                if num_tracks > 0:
                    # Determine the target music index based on intensity
                    target_music_index = int(intensity * num_tracks)
                    target_music_index = min(target_music_index, num_tracks - 1)

                    target_melody_track = melody_tracks[target_music_index]
                    
                    # Check if the target track is different or if the music stopped playing
                    if music_channel_melody.get_sound() != target_melody_track or not music_channel_melody.get_busy():
                        current_music_index = target_music_index
                        music_channel_melody.play(target_melody_track)
                        # Ensure bass track index is valid
                        if target_music_index < len(bass_tracks):
                            music_channel_bass.play(bass_tracks[target_music_index])

        
        if game_active:
            # --- Spawning Logic ---
            current_time = pygame.time.get_ticks()
            if current_time - last_spawn_time > spawn_cooldown:
                # Pass the rival count to spawn_entity for scaling and Diamond logic
                new_entity = spawn_entity(player.kills, total_entities_spawned, rivals_spawned_count)
                
                # Add entity to the correct list
                if isinstance(new_entity, RivalCircle):
                    rivals.append(new_entity)
                    rivals_spawned_count += 1 # Increment the count for the next spawn/logic check
                else:
                    # All other enemies (Squares, Triangles, Diamonds) go here
                    enemies.append(new_entity)
                
                total_entities_spawned += 1
                last_spawn_time = current_time
                
                # Update spawn cooldown (Difficulty scaling based on kills)
                spawn_cooldown = max(MIN_SPAWN_COOLDOWN, INITIAL_SPAWN_COOLDOWN - player.kills * SPAWN_COOLDOWN_REDUCTION_PER_KILL)

            # --- Entity Updates ---
            
            # Player Update
            player.move()
            # Player shoots at both standard enemies and rivals
            player.shoot(enemies + rivals, bullets, shot_sound)
            
            # Item Collection & Bomb Activation
            bomb_activated = False
            # Iterate over a copy of the list for safe removal
            for item in items[:]:
                if player.rect.colliderect(item.rect):
                    if item.type == 'bomb':
                        bomb_activated = True
                    else:
                        player.collect_item(item)
                    items.remove(item)

            # --- BOMB LOGIC (Handles Immunity and Duplication) ---
            if bomb_activated:
                # Play sound and trigger visuals
                channel = pygame.mixer.find_channel(True)
                if channel: channel.play(bomb_sound)
                flash_alpha = 200 

                # Identify entities that will be destroyed and those that react differently
                to_destroy = []
                reacting_entities = [] # Primarily Diamonds

                # Check all standard enemies
                for entity in enemies:
                    # Call handle_bomb() which returns True if destroyed, False otherwise
                    if entity.handle_bomb():
                        to_destroy.append(entity)
                    else:
                        # If not destroyed, it reacted (e.g., Diamond duplicated)
                        reacting_entities.append(entity)

                # Rivals are always destroyed by bombs
                for rival in rivals:
                    to_destroy.append(rival)

                # Use a set for efficient management of destruction, handling cascading deaths (splits)
                destruction_set = set(to_destroy)
                
                # Track where to spawn the replacement bomb (location of the first rival destroyed)
                bomb_spawn_location = None

                # Process Destruction
                while destruction_set:
                    target = destruction_set.pop()

                    # Handle Rival specific logic
                    if isinstance(target, RivalCircle):
                        if bomb_spawn_location is None:
                            bomb_spawn_location = (target.x, target.y)
                        
                        # Safely remove from the rivals list
                        if target in rivals:
                            rivals.remove(target)
                    
                    # Handle standard enemies
                    else:
                        # Handle potential splits (e.g., Triangles)
                        new_splits = target.on_death()
                        # Add splits to the destruction list so they die immediately too
                        for split in new_splits:
                            # Add splits to the main enemy list and the destruction set
                            enemies.append(split) 
                            destruction_set.add(split)
                        
                        # Safely remove from the enemies list
                        if target in enemies:
                            enemies.remove(target)

                # Spawn exactly one replacement bomb if any rivals were killed
                if bomb_spawn_location:
                    items.append(Item(bomb_spawn_location[0], bomb_spawn_location[1], player.kills, item_type='bomb'))

                # --- Handle Duplication (Post-Bomb Effects) ---
                new_duplicates = []
                # Deterministic counter for offset
                duplication_count = 0
                for entity in reacting_entities:
                    # Specific check for Diamond duplication flag
                    if isinstance(entity, DiamondEnemy) and entity.duplication_pending:
                        # Create a new diamond slightly offset.
                        # Deterministic offset (alternating left/right based on count)
                        offset_x = 15 if (duplication_count % 2 == 0) else -15
                        duplication_count += 1
                        
                        # Create the duplicate, ensuring it inherits max_health correctly
                        duplicate = DiamondEnemy(entity.x + offset_x, entity.y, entity.max_health)
                        duplicate.health = entity.health # Inherit current health
                        
                        new_duplicates.append(duplicate)
                        entity.duplication_pending = False # Reset flag

                # Add the newly created duplicates to the main enemy list
                enemies.extend(new_duplicates)

            # ----------------------------------------------------------------

            # Enemy AI Update (Strategic Swarm and Evasion)
            # Pass the full list of standard enemies (obstacles) and player bullets (threats)
            for enemy in enemies:
                # 'enemies' list is passed as obstacles for separation logic
                # 'bullets' list is passed for evasion logic (used by Squares)
                enemy.strategic_move(player, enemies, bullets)
            
            # Rival AI Update (Aggressive Player Hunting)
            # Rivals avoid standard enemies (obstacles). They currently ignore player bullets for movement.
            for rival in rivals: 
                rival.strategic_move(player, enemies, bullets)
                # MODIFIED: Pass 'enemies' list to shoot method for targeting
                rival.shoot(player, enemies, rival_bullets, shot_sound)
            
            # Bullet Updates
            for b in bullets + rival_bullets:
                b.move()
            
            # --- Collision Detection ---
            
            # Player Bullets (vs Enemies and Rivals)
            for bullet in bullets[:]:
                if bullet.is_offscreen():
                    if bullet in bullets: bullets.remove(bullet)
                    continue
                
                # Combine all targets, iterating over copies as lists might change
                all_targets = enemies[:] + rivals[:]
                for target in all_targets:
                    # Ensure target still exists (might have been removed in a previous iteration or by bomb)
                    if (target in enemies or target in rivals) and bullet.rect.colliderect(target.rect):
                        
                        # Play hit sound
                        channel = pygame.mixer.find_channel(True)
                        if channel: channel.play(hit_sound)
                        
                        # Apply damage
                        if target.take_damage(bullet.damage):
                            # Handle Death
                            player.kills += 1
                            
                            # NEW: Check for Multishot Item Drop
                            if player.kills > 0 and player.kills % 50 == 0:
                                items.append(Item(target.x, target.y, item_type='multishot'))

                            # Play death sound
                            channel = pygame.mixer.find_channel(True)
                            if channel: channel.play(death_sound)
                            
                            # Item/Bomb Drop Logic
                            if isinstance(target, RivalCircle):
                                # Rivals always drop a bomb when killed by player
                                items.append(Item(target.x, target.y, player.kills, item_type='bomb'))
                            elif math.hypot(player.x - target.x, player.y - target.y) <= player.item_drop_range:
                                # Standard enemies (including Diamonds) drop standard items if close enough
                                items.append(Item(target.x, target.y, player.kills))
                            
                            # Handle splitting (Triangles)
                            new_enemies = target.on_death()
                            enemies.extend(new_enemies)
                            
                            # Remove the target from the correct list
                            if isinstance(target, RivalCircle):
                                if target in rivals: rivals.remove(target)
                            else:
                                if target in enemies: enemies.remove(target)
                        
                        # Remove the bullet after impact
                        if bullet in bullets: bullets.remove(bullet)
                        break # Move to the next bullet

            # Rival Bullets (vs Player and Enemies)
            for bullet in rival_bullets[:]:
                if bullet.is_offscreen():
                    if bullet in rival_bullets: rival_bullets.remove(bullet)
                    continue
                
                # Check against Player (Game Over condition)
                if bullet.rect.colliderect(player.rect):
                    game_active = False
                    # Stop music on game over
                    music_channel_melody.stop()
                    music_channel_bass.stop()
                    if bullet in rival_bullets: rival_bullets.remove(bullet)
                    continue

                # Check against Enemies (Friendly Fire)
                # Rivals bullets damage standard enemies (including Diamonds)
                for enemy in enemies[:]:
                    if enemy in enemies and bullet.rect.colliderect(enemy.rect):
                        
                        # Play hit sound
                        channel = pygame.mixer.find_channel(True)
                        if channel: channel.play(hit_sound)
                        
                        # Apply damage (Rival bullets deal 1 damage)
                        if enemy.take_damage(1):
                            # Handle death effects (Splitting)
                            new_splits = enemy.on_death()
                            enemies.extend(new_splits)
                            if enemy in enemies: enemies.remove(enemy)
                        
                        # Remove bullet
                        if bullet in rival_bullets: rival_bullets.remove(bullet)
                        break

            
            # Physical Collision (Player vs Enemies/Rivals)
            for unit in enemies[:] + rivals[:]:
                # Check existence and collision
                if (unit in enemies or unit in rivals) and player.rect.colliderect(unit.rect):
                    game_active = False
                    music_channel_melody.stop()
                    music_channel_bass.stop()
                    break

            # Physical Collision (Rivals vs Enemies) - Mutual Destruction
            # Iterate over copies for safe removal
            for rival in rivals[:]:
                # Check if rival still exists
                if rival not in rivals: continue
                
                for enemy in enemies[:]:
                    # Check if enemy still exists
                    if enemy not in enemies: continue
                    
                    # Check collision
                    if rival.rect.colliderect(enemy.rect):
                        # Mutual destruction (Applies to all standard enemies, including Diamonds)
                        
                        # Play death sound
                        channel = pygame.mixer.find_channel(True)
                        if channel: channel.play(death_sound)

                        # Rival drops bomb on mutual destruction too
                        items.append(Item(rival.x, rival.y, player.kills, item_type='bomb'))
                        
                        # Handle enemy death effects (Splitting)
                        new_splits = enemy.on_death()
                        enemies.extend(new_splits)

                        # Remove both entities safely
                        if rival in rivals: rivals.remove(rival)
                        if enemy in enemies: enemies.remove(enemy)
                        
                        break # Move to the next rival

            # --- Drawing ---
            screen.fill(BACKGROUND_COLOR)
            
            # Draw entities in specific order (Items -> Enemies -> Player -> Bullets)
            # Pass the specific fonts required for drawing text/health bars
            for item in items:
                item.draw(screen, item_font)
            for enemy in enemies:
                enemy.draw(screen, enemy_font)
            for rival in rivals:
                rival.draw(screen, enemy_font)
                
            player.draw(screen)
            
            for b in bullets + rival_bullets:
                b.draw(screen)
                
            # Draw UI on top
            draw_ui(screen, player, ui_font, spawn_cooldown, rivals_spawned_count)

            # Draw Flash effect (if active)
            if flash_alpha > 0:
                flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                # Ensure alpha doesn't exceed 255
                flash_surface.fill((255, 255, 255, min(flash_alpha, 255)))
                screen.blit(flash_surface, (0, 0))
                flash_alpha = max(0, flash_alpha - 20) # Fade out quickly
            
        else:
            # Game Over State
            draw_game_over(screen, player.kills, ui_font, go_font_big)

        # Update the display
        pygame.display.flip()
        # Cap the frame rate
        clock.tick(FPS)

# --- Initialization Helper ---

def initialize_audio():
    # Initialize Mixer with specific settings
    try:
        # Use a smaller buffer size (512) to reduce latency
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        # Set a sufficient number of channels for overlapping sounds
        pygame.mixer.set_num_channels(16)
    except pygame.error as e:
        print(f"Audio initialization failed: {e}")
        # Return dummy assets if mixer fails to allow the game to run silently
        dummy_channel = DummyChannel()
        return {
            'melodies': [DummySound()], 'bass': [DummySound()], 'shot': DummySound(), 'hit': DummySound(), 'death': DummySound(),
            'bomb': DummySound(), 'rival_melody': DummySound(), 'rival_bass': DummySound(),
            'channel_melody': dummy_channel, 'channel_bass': dummy_channel
        }

    print("Generating Audio Assets...")

    # Define Music (C Minor scale for tension)
    notes = {
        'C3': 130.81, 'D3': 146.83, 'Eb3': 155.56, 'F3': 174.61, 'G3': 196.00, 'Ab3': 207.65, 'Bb3': 233.08,
        'C4': 261.63, 'D4': 293.66, 'Eb4': 311.13, 'F4': 349.23, 'G4': 392.00, 'Ab4': 415.30, 'Bb4': 466.16,
        'C5': 523.25, 'D5': 587.33, 'Eb5': 622.25, 'F5': 698.46, 'G5': 783.99
    }
    # Note durations (sn=Sixteenth note, en=Eighth note, qn=Quarter note, hn=Half note)
    sn = 0.075; en = 0.15; qn = 0.30; hn = 0.60

    # 4 distinct musical segments for dynamic intensity
    # (Music definitions remain the same)
    # Segment 1 (Low Intensity)
    melody1 = [
        (notes['C4'], qn), (notes['Eb4'], qn), (notes['G4'], qn), (notes['Ab4'], en), (notes['G4'], en),
        (notes['F4'], hn), (notes['Eb4'], hn)
    ]
    bass1 = [
        (notes['C3'], hn), (notes['C3'], hn),
        (notes['F3'], hn), (notes['Ab3'], hn)
    ]

    # Segment 2 (Medium Intensity)
    melody2 = [
        (notes['C4'],en),(notes['Eb4'],en),(notes['G4'],en),(notes['C5'],en), (notes['C4'],en),(notes['Eb4'],en),(notes['G4'],en),(notes['C5'],en),
        (notes['Bb3'],en),(notes['D4'],en),(notes['F4'],en),(notes['Bb4'],en), (notes['Bb3'],en),(notes['D4'],en),(notes['F4'],en),(notes['Bb4'],en)
    ]
    bass2 = [
        (notes['C3'], qn), (notes['G3'], qn), (notes['C3'], qn), (notes['G3'], qn),
        (notes['Bb3'], qn), (notes['F3'], qn), (notes['Bb3'], qn), (notes['F3'], qn)
    ]

    # Segment 3 (High Intensity)
    melody3 = [
        (notes['G4'], qn), (notes['Ab4'], en), (notes['Bb4'], en), (notes['C5'], qn), (notes['Bb4'], en), (notes['Ab4'], en),
        (notes['G4'], qn), (notes['F4'], qn), (notes['Eb4'], qn), (notes['D4'], qn)
    ]
    bass3 = [
        (notes['Eb3'], hn), (notes['F3'], hn),
        (notes['G3'], hn), (notes['Bb3'], hn)
    ]

    # Segment 4 (Max Intensity)
    melody4 = [
        (notes['C5'],en),(notes['Eb5'],en),(notes['C5'],en),(notes['Ab4'],en), (notes['G4'],en),(notes['F4'],en),(notes['G4'],en),(notes['Ab4'],en),
        (notes['Bb4'],en),(notes['D5'],en),(notes['Bb4'],en),(notes['G4'],en), (notes['F4'],en),(notes['Eb4'],en),(notes['F4'],en),(notes['G4'],en)
    ]
    bass4 = [
        (notes['C3'], en), (notes['C3'], en), (notes['C3'], en), (notes['C3'], en), (notes['F3'], en), (notes['F3'], en), (notes['F3'], en), (notes['F3'], en),
        (notes['G3'], en), (notes['G3'], en), (notes['G3'], en), (notes['G3'], en), (notes['Ab3'], en), (notes['Ab3'], en), (notes['Ab3'], en), (notes['Ab3'], en)
    ]

    # RIVAL THEME (Fast, high-pitched, aggressive)
    melody_rival = [
        (notes['G5'], sn), (notes['F5'], sn), (notes['Eb5'], sn), (notes['D5'], sn), (notes['C5'], sn), (notes['D5'], sn), (notes['Eb5'], sn), (notes['F5'], sn),
        (notes['G5'], sn), (notes['Ab4'], sn), (notes['G5'], sn), (notes['Ab4'], sn), (notes['G5'], sn), (notes['F5'], sn), (notes['Eb5'], sn), (notes['D5'], sn)
    ]
    # Bass is very fast and repetitive
    bass_rival = [
        (notes['C3'], sn), (notes['C3'], sn), (notes['Eb3'], sn), (notes['C3'], sn), (notes['F3'], sn), (notes['C3'], sn), (notes['Eb3'], sn), (notes['C3'], sn),
        (notes['Ab3'], sn), (notes['Ab3'], sn), (notes['G3'], sn), (notes['G3'], sn), (notes['F3'], sn), (notes['F3'], sn), (notes['Eb3'], sn), (notes['Eb3'], sn)
    ]


    try:
        # Generate the sound objects for music tracks
        melody_tracks = [generate_full_melody_sound(m, wave_type='sine') for m in [melody1, melody2, melody3, melody4]]
        bass_tracks = [generate_bass_track(b, wave_type='soft_square') for b in [bass1, bass2, bass3, bass4]]
        
        # Generate Rival Music (Slightly louder melody for emphasis)
        rival_melody = generate_full_melody_sound(melody_rival, wave_type='sine', amplitude=0.25)
        rival_bass = generate_bass_track(bass_rival, wave_type='soft_square')

        # Generate Sound Effects
        shot_sound = generate_laser_sound()
        
        # Hit sound (Short sine wave blip)
        hit_sound_array = generate_sound_array(300, 0.05, wave_type='sine', amplitude=0.4)
        if hit_sound_array.size > 0 and pygame.mixer.get_init():
            hit_sound = pygame.sndarray.make_sound(np.ascontiguousarray(np.vstack((hit_sound_array, hit_sound_array)).T))
        else:
            hit_sound = DummySound()
        
        # Death sound (Textured noise burst)
        death_sound_array = generate_sound_array(80, 0.2, wave_type='noise', amplitude=0.5)
        if death_sound_array.size > 0 and pygame.mixer.get_init():
            death_sound = pygame.sndarray.make_sound(np.ascontiguousarray(np.vstack((death_sound_array, death_sound_array)).T))
        else:
            death_sound = DummySound()

        # Bomb Sound (Deeper and louder explosion)
        bomb_sound = generate_explosion_sound()

        
        # Reserve specific channels for music (Channel 0 for Melody, Channel 1 for Bass)
        music_channel_melody = pygame.mixer.Channel(0)
        music_channel_bass = pygame.mixer.Channel(1)

        print("Audio Ready.")
        return {
            'melodies': melody_tracks,
            'bass': bass_tracks,
            'rival_melody': rival_melody,
            'rival_bass': rival_bass,
            'shot': shot_sound,
            'hit': hit_sound,
            'death': death_sound,
            'bomb': bomb_sound,
            'channel_melody': music_channel_melody,
            'channel_bass': music_channel_bass
        }
    except Exception as e:
        print(f"An error occurred during audio generation: {e}. Proceeding without sound.")
        # Return dummy assets if generation fails
        dummy_channel = DummyChannel()
        return {
            'melodies': [DummySound()], 'bass': [DummySound()], 'shot': DummySound(), 'hit': DummySound(), 'death': DummySound(),
            'bomb': DummySound(), 'rival_melody': DummySound(), 'rival_bass': DummySound(),
            'channel_melody': dummy_channel, 'channel_bass': dummy_channel
        }


if __name__ == "__main__":
    # Initialize Pygame modules
    pygame.init()
    
    # Set up display
    try:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("MADNESS")
    except pygame.error as e:
        print(f"Failed to initialize display: {e}")
        sys.exit(1)
        
    clock = pygame.time.Clock()

    # Initialize and load/generate audio assets
    # This handles audio initialization and generation robustly
    audio_assets = initialize_audio()

    # Start with the title screen
    title_screen(screen, clock)

    # Main game loop (restarts automatically when game_loop returns)
    while True:
        game_loop(screen, clock, audio_assets)
import pygame
import sys
import math
import numpy as np

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# --- Colors ---
# Softer color palette inspired by retro-futurism
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
# Health Bar
HEALTH_BAR_BG = (50, 50, 50)
HEALTH_BAR_FG = (80, 255, 80)
# Items
ITEM_COLORS = {'speed': (0, 191, 255), 'range': (255, 215, 0), 'damage': (255, 69, 0)}

# --- Game Settings ---
PLAYER_RADIUS = 12
PLAYER_START_SPEED = 4.0
PLAYER_START_ATTACK_RANGE = 120
PLAYER_ITEM_DROP_RANGE = 60
PLAYER_START_DAMAGE = 1
PLAYER_SHOOT_COOLDOWN = 300 # Slightly slower initially
SQUARE_START_HEALTH = 3
TRIANGLE_START_HEALTH = 2
TRIANGLE_START_SPEED = 2.0
TRIANGLE_SPAWN_THRESHOLD = 10
RIVAL_SPAWN_THRESHOLD = 25
RIVAL_START_HEALTH = 10 # Rivals are tougher
RIVAL_SPEED = 3.5
RIVAL_ATTACK_RANGE = 150
RIVAL_SHOOT_COOLDOWN = 500
BULLET_RADIUS = 4
BULLET_SPEED = 12
INITIAL_SPAWN_COOLDOWN = 2000
MIN_SPAWN_COOLDOWN = 250
SPAWN_COOLDOWN_REDUCTION_PER_KILL = 20
ITEM_RADIUS = 8

# --- AI Settings ---
# How strongly enemies try to avoid each other (Swarm behavior)
SEPARATION_FORCE = 0.5
SEPARATION_RADIUS = 40
# How strongly the Rival avoids the player while positioning
RIVAL_PLAYER_AVOIDANCE_RADIUS = 100
RIVAL_OPTIMAL_FIRING_DISTANCE = 130

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

    # Coefficients (a*t^2 + b*t + c = 0)
    a = target_vx**2 + target_vy**2 - bullet_speed**2
    b = 2 * (dx * target_vx + dy * target_vy)
    c = dx**2 + dy**2

    # If 'a' is near zero, speeds are similar; fallback to direct aiming.
    if abs(a) < 1e-6:
        time_to_impact = math.hypot(dx, dy) / bullet_speed if bullet_speed > 0 else 0
    else:
        # Discriminant (b^2 - 4ac)
        discriminant = b**2 - 4*a*c

        if discriminant < 0:
            # No real solution, fallback
             time_to_impact = math.hypot(dx, dy) / bullet_speed if bullet_speed > 0 else 0
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
                time_to_impact = math.hypot(dx, dy) / bullet_speed if bullet_speed > 0 else 0

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

    # Player shooting remains automatic, targeting the closest enemy
    def shoot(self, enemies, bullets, shot_sound):
        current_time = pygame.time.get_ticks()
        if not enemies or current_time - self.last_shot_time < PLAYER_SHOOT_COOLDOWN:
            return
        
        all_targets = enemies
        # Deterministic targeting: Closest enemy
        closest_target = min(all_targets, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
        distance = math.hypot(closest_target.x - self.x, closest_target.y - self.y)

        if distance <= self.attack_range:
            # The player also uses predictive aiming
            predicted_x, predicted_y = predict_target_position(
                self.x, self.y,
                closest_target.x, closest_target.y,
                closest_target.vx, closest_target.vy,
                BULLET_SPEED
            )
            
            dx, dy = predicted_x - self.x, predicted_y - self.y
            
            bullets.append(Bullet(self.x, self.y, dx, dy, self.damage, BULLET_COLOR))
            self.last_shot_time = current_time
            pygame.mixer.find_channel(True).play(shot_sound)

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
        if item.type == 'speed': self.speed += 0.3
        elif item.type == 'range': self.attack_range += 10
        elif item.type == 'damage': self.damage += 1

class Bullet:
    def __init__(self, x, y, target_dx, target_dy, damage, color):
        self.x, self.y = x, y
        self.radius, self.speed, self.damage, self.color = BULLET_RADIUS, BULLET_SPEED, damage, color
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
    def __init__(self, x, y, kill_count):
        self.x, self.y = x, y
        self.radius = ITEM_RADIUS
        # Deterministic item drops based on kill count modulo 3
        item_types = ['speed', 'range', 'damage']
        self.type = item_types[kill_count % 3]
        self.color = ITEM_COLORS[self.type]
        self.rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
        self.creation_time = pygame.time.get_ticks()

    def draw(self, screen, font):
        # Add a subtle pulsing effect
        time_elapsed = pygame.time.get_ticks() - self.creation_time
        pulse = math.sin(time_elapsed * 0.005) * 2
        draw_radius = self.radius + pulse
        
        pygame.draw.circle(screen, self.color, (self.x, self.y), draw_radius)
        # Use the first letter of the type as an indicator
        letter_surf = font.render(self.type[0].upper(), True, (0,0,0))
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

        # Cap speed if necessary (important when forces combine)
        current_speed = math.hypot(self.vx, self.vy)
        if current_speed > self.speed * 1.5: # Allow temporary burst over max speed
             scale = (self.speed * 1.5) / current_speed
             self.vx *= scale
             self.vy *= scale
             
    def update_position(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (self.x, self.y)
    
    # Strategic movement logic for basic enemies (Swarm behavior)
    def strategic_move(self, player, all_enemies):
        # 1. Attraction (Move towards the player)
        attraction_dx = player.x - self.x
        attraction_dy = player.y - self.y
        attraction_vx, attraction_vy = normalize_vector(attraction_dx, attraction_dy)
        
        # 2. Separation (Avoid crowding other enemies)
        # This prevents enemies from clustering into a single point, making them surround the player.
        separation_fx, separation_fy = 0, 0
        for other in all_enemies:
            if other == self:
                continue
            
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
        # The primary goal is attraction, separation modifies the path
        self.vx = attraction_vx * self.speed
        self.vy = attraction_vy * self.speed
        
        # Apply separation force
        self.apply_force(separation_fx, separation_fy)
        self.update_position()

        
    def take_damage(self, amount):
        self.health -= amount
        return self.health <= 0

    def draw_health_bar(self, screen, font):
        # Only draw health bar if damaged
        if self.health < self.max_health:
            bar_width, bar_height = self.size, 4
            health_pct = max(0, self.health / self.max_health)
            
            # Position above the entity
            bar_x = self.x - bar_width / 2
            bar_y = self.y - self.size / 2 - bar_height - 5
            
            bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_BG, bg_rect)
            
            fg_rect = pygame.Rect(bar_x, bar_y, bar_width * health_pct, bar_height)
            pygame.draw.rect(screen, HEALTH_BAR_FG, fg_rect)

    def on_death(self): return []

class SquareEnemy(Enemy):
    def __init__(self, x, y, health):
        super().__init__(x, y, 25, 1.5, health, SQUARE_COLOR)
        
    def draw(self, screen, font):
        # Rotate the square based on movement direction for visual flair
        angle = math.degrees(math.atan2(self.vy, self.vx))
        rotated_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.rect(rotated_surface, self.color, (0, 0, self.size, self.size))
        rotated_image = pygame.transform.rotate(rotated_surface, -angle)
        new_rect = rotated_image.get_rect(center = self.rect.center)
        screen.blit(rotated_image, new_rect.topleft)
        
        self.draw_health_bar(screen, font)

class TriangleEnemy(Enemy):
    def __init__(self, x, y, health, size):
        # Triangle speed is faster than squares
        speed = TRIANGLE_START_SPEED * (1.5 if size < 30 else 1.0) # Smaller ones are faster
        super().__init__(x, y, size, speed, health, TRIANGLE_COLOR)

    def draw(self, screen, font):
        # Calculate points for an equilateral triangle centered at (self.x, self.y)
        height = self.size * (math.sqrt(3)/2)
        # Points relative to the center
        p1 = (0, -height / 2) # Top
        p2 = (-self.size / 2, height / 2) # Bottom left
        p3 = (self.size / 2, height / 2) # Bottom right
        
        # Rotate the triangle based on movement direction
        angle = math.atan2(self.vy, self.vx) - math.pi/2 # Adjust by 90 degrees so the tip points forward

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

class RivalCircle(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 20, RIVAL_SPEED, RIVAL_START_HEALTH, RIVAL_COLOR)
        self.attack_range = RIVAL_ATTACK_RANGE
        self.last_shot_time = 0
        self.target = None # Current strategic target

    # Advanced strategic movement for the Rival
    def strategic_move(self, player, enemies):
        # The Rival's goal is complex: eliminate enemies efficiently while maintaining a safe distance from the player.
        
        # 1. Target Selection (Deterministic Prioritization)
        # STRATEGY: Prioritize the enemy that is closest to the player, as this poses the greatest threat.
        if enemies:
            self.target = min(enemies, key=lambda e: math.hypot(e.x - player.x, e.y - player.y))
        else:
            self.target = None

        # 2. Positioning relative to the target
        if self.target:
            # Maintain optimal firing distance from the target
            distance_to_target = math.hypot(self.target.x - self.x, self.target.y - self.y)
            
            # Vector towards target
            tx, ty = normalize_vector(self.target.x - self.x, self.target.y - self.y)
            
            if distance_to_target > RIVAL_OPTIMAL_FIRING_DISTANCE:
                # Move closer
                move_x, move_y = tx * self.speed, ty * self.speed
            elif distance_to_target < RIVAL_OPTIMAL_FIRING_DISTANCE - 20:
                # Move away (Kiting)
                move_x, move_y = -tx * self.speed, -ty * self.speed
            else:
                # Strafe around the target (move perpendicularly - deterministic direction)
                move_x, move_y = ty * self.speed * 0.5, -tx * self.speed * 0.5
        else:
            # If no targets, move towards the center of the screen (Patrol)
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            move_x, move_y = normalize_vector(center_x - self.x, center_y - self.y)
            move_x *= self.speed * 0.5
            move_y *= self.speed * 0.5

        # 3. Player Avoidance (Safety Override)
        # STRATEGY: The Rival treats the player as a threat and actively avoids getting close.
        distance_to_player = math.hypot(player.x - self.x, player.y - self.y)
        if distance_to_player < RIVAL_PLAYER_AVOIDANCE_RADIUS:
            # Calculate avoidance force
            avoidance_strength = 1.0 - (distance_to_player / RIVAL_PLAYER_AVOIDANCE_RADIUS)
            avoid_x, avoid_y = normalize_vector(self.x - player.x, self.y - player.y)
            
            # Blend strategic movement with strong avoidance
            self.vx = move_x * (1 - avoidance_strength) + avoid_x * self.speed * avoidance_strength
            self.vy = move_y * (1 - avoidance_strength) + avoid_y * self.speed * avoidance_strength
        else:
            self.vx = move_x
            self.vy = move_y

        # Normalize final velocity if it exceeds max speed
        final_speed = math.hypot(self.vx, self.vy)
        if final_speed > self.speed:
            scale = self.speed / final_speed
            self.vx *= scale
            self.vy *= scale
            
        self.update_position()

    def shoot(self, rival_bullets, shot_sound):
        current_time = pygame.time.get_ticks()
        if not self.target or current_time - self.last_shot_time < RIVAL_SHOOT_COOLDOWN:
            return
        
        distance = math.hypot(self.target.x - self.x, self.target.y - self.y)

        if distance <= self.attack_range:
            # Use predictive aiming
            predicted_x, predicted_y = predict_target_position(
                self.x, self.y,
                self.target.x, self.target.y,
                self.target.vx, self.target.vy,
                BULLET_SPEED
            )

            dx = predicted_x - self.x
            dy = predicted_y - self.y
            
            rival_bullets.append(Bullet(self.x, self.y, dx, dy, 1, RIVAL_BULLET_COLOR))
            self.last_shot_time = current_time
    
    def draw(self, screen, font):
        # Draw Attack Range (very faint)
        range_surface = pygame.Surface((self.attack_range * 2, self.attack_range * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surface, self.color + (20,), (self.attack_range, self.attack_range), self.attack_range)
        screen.blit(range_surface, (self.x - self.attack_range, self.y - self.attack_range))
        
        # Draw Rival Circle
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size // 2)
        self.draw_health_bar(screen, font)

# --- Audio Generation (Improved) ---

def generate_sound_array(frequency, duration, sample_rate=44100, amplitude=0.5, wave_type='sine'):
    num_samples = int(sample_rate * duration)
    time_array = np.linspace(0., duration, num_samples, endpoint=False)
    
    # Use Sine waves for a softer, less harsh sound
    if wave_type == 'sine':
        # Basic Sine Wave
        wave = np.sin(2 * np.pi * frequency * time_array)
    elif wave_type == 'soft_square':
        # Approximation of a square wave using Fourier series (fewer harmonics) for a richer bass sound
        wave = np.sin(2 * np.pi * frequency * time_array)
        wave += (1/3) * np.sin(2 * np.pi * 3 * frequency * time_array)
        wave += (1/5) * np.sin(2 * np.pi * 5 * frequency * time_array)
    elif wave_type == 'noise':
        # Deterministic noise generation is required.
        # We use a frequency modulated sine wave for a deterministic noise-like effect for explosions.
        mod_freq = 50
        mod_wave = np.sin(2 * np.pi * mod_freq * time_array)
        wave = np.sin(2 * np.pi * (frequency + mod_wave*20) * time_array)
    else:
        wave = np.sin(2 * np.pi * frequency * time_array)
        
    # Apply fade out (Envelope)
    fade_out = np.linspace(1., 0., num_samples)**1.5 # Softer fade
    wave *= fade_out
    
    # Normalize and convert to 16-bit PCM
    # Check for silence before normalizing
    max_abs = np.max(np.abs(wave))
    wave = wave / max_abs if max_abs > 0 else wave 
    sound_data = (wave * (2**15 - 1) * amplitude).astype(np.int16)
    return sound_data

def generate_full_melody_sound(note_sequence, sample_rate=44100, amplitude=0.2, wave_type='sine'):
    # Generate the melody track
    melody_arrays = [generate_sound_array(freq, dur, sample_rate, amplitude, wave_type) for freq, dur in note_sequence]
    full_melody_array = np.concatenate(melody_arrays)
    
    # Create a stereo sound (Melody slightly panned for better separation from bass)
    left_channel = (full_melody_array * 0.8).astype(np.int16)
    right_channel = (full_melody_array * 0.5).astype(np.int16)
    
    stereo_melody_array = np.ascontiguousarray(np.vstack((left_channel, right_channel)).T)
    return pygame.sndarray.make_sound(stereo_melody_array)

def generate_bass_track(note_sequence, sample_rate=44100, amplitude=0.3, wave_type='soft_square'):
     # Generate the bass track (using a different waveform)
    bass_arrays = [generate_sound_array(freq, dur, sample_rate, amplitude, wave_type) for freq, dur in note_sequence]
    full_bass_array = np.concatenate(bass_arrays)
    
    # Create a stereo sound (Bass centered)
    stereo_bass_array = np.ascontiguousarray(np.vstack((full_bass_array, full_bass_array)).T)
    return pygame.sndarray.make_sound(stereo_bass_array)


def generate_laser_sound(duration=0.1, start_freq=600, end_freq=300):
    # Softer laser sound
    sample_rate=44100
    num_samples = int(sample_rate * duration)
    # Frequency sweep
    frequency = np.linspace(start_freq, end_freq, num_samples)
    # Generate wave (Sine) - np.cumsum is used here for the frequency sweep integration
    wave = np.sin(2 * np.pi * np.cumsum(frequency) / sample_rate)
    
    # Envelope (Fade out)
    fade = np.linspace(1., 0., num_samples)**2
    wave *= fade
    
    sound_data = (wave * (2**15 - 1) * 0.3).astype(np.int16) # Lower amplitude
    stereo_sound_data = np.ascontiguousarray(np.vstack((sound_data, sound_data)).T)
    return pygame.sndarray.make_sound(stereo_sound_data)

# --- Game Logic Functions ---

def spawn_entity(player_kills, total_entities_spawned):
    # Deterministic spawning based on total entities spawned
    # Spawns sequentially around the edges of the screen
    spawn_sides = ['top', 'right', 'bottom', 'left']
    side = spawn_sides[total_entities_spawned % 4]
    
    # Use a simple deterministic position along the edge
    position_seed = (total_entities_spawned * 137) 
    
    if side == 'top':
        x, y = position_seed % SCREEN_WIDTH, -30
    elif side == 'bottom':
        x, y = position_seed % SCREEN_WIDTH, SCREEN_HEIGHT + 30
    elif side == 'left':
        x, y = -30, position_seed % SCREEN_HEIGHT
    else: # right
        x, y = SCREEN_WIDTH + 30, position_seed % SCREEN_HEIGHT
    
    # Deterministic enemy type selection based on kill thresholds and spawn count
    
    # Spawn a Rival every 10 spawns after the threshold
    if player_kills >= RIVAL_SPAWN_THRESHOLD and (total_entities_spawned + 1) % 10 == 0:
        return RivalCircle(x, y)
    
    # Spawn a Triangle every 5 spawns after the threshold
    elif player_kills >= TRIANGLE_SPAWN_THRESHOLD and (total_entities_spawned + 1) % 5 == 0:
        # Increase health scaling slightly faster for triangles
        health = TRIANGLE_START_HEALTH + (player_kills // 12)
        return TriangleEnemy(x, y, health, 30)
    
    else:
        # Default spawn: Square
        # Increase health scaling based on kills
        health = SQUARE_START_HEALTH + (player_kills // 15)
        return SquareEnemy(x, y, health)

def calculate_intensity(spawn_cooldown):
    # Calculates intensity based on how close the spawn cooldown is to the minimum
    if (INITIAL_SPAWN_COOLDOWN - MIN_SPAWN_COOLDOWN) > 0:
        intensity = (INITIAL_SPAWN_COOLDOWN - spawn_cooldown) / (INITIAL_SPAWN_COOLDOWN - MIN_SPAWN_COOLDOWN)
    else:
        intensity = 1.0 # Handle case where initial == min
    return intensity

def draw_ui(screen, player, font, spawn_cooldown):
    # Display Kills
    score_text = font.render(f"Kills: {player.kills}", True, TEXT_COLOR)
    screen.blit(score_text, (10, 10))
    
    # Display Stats
    stats_y = 40
    stats = [
        (f"Speed: {player.speed:.1f}", ITEM_COLORS['speed']),
        (f"Range: {player.attack_range}", ITEM_COLORS['range']),
        (f"Damage: {player.damage}", ITEM_COLORS['damage'])
    ]
    for text, color in stats:
        surf = font.render(text, True, color)
        screen.blit(surf, (10, stats_y))
        stats_y += 25

    # Display Intensity indicator
    intensity = calculate_intensity(spawn_cooldown)
    intensity_text = font.render(f"Intensity: {intensity*100:.0f}%", True, TEXT_COLOR)
    screen.blit(intensity_text, (SCREEN_WIDTH - 150, 10))


def draw_game_over(screen, score, font, big_font):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180)) # Darker overlay
    screen.blit(overlay, (0, 0))
    
    title = big_font.render("YOU WERE OVERWHELMED", True, SQUARE_COLOR)
    score_text = font.render(f"Final Kills: {score}", True, TEXT_COLOR)
    restart_text = font.render("Press R to restart", True, TEXT_COLOR)
    
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 3))
    screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2))
    screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

def title_screen(screen, clock):
    title_font = pygame.font.Font(None, 150)
    subtitle_font = pygame.font.Font(None, 36)
    
    title_text = title_font.render("MADNESS", True, RIVAL_COLOR)
    subtitle_text = subtitle_font.render("Press any key to begin", True, TEXT_COLOR)
    
    # Simple background animation (Deterministic moving shapes)
    squares = []
    for i in range(10):
        # Deterministic initial positions
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
            # Move deterministically
            dx = math.cos(math.radians(square['angle'])) * square['speed']
            dy = math.sin(math.radians(square['angle'])) * square['speed']
            square['rect'].x += dx
            square['rect'].y += dy
            
            # Wrap around screen
            if square['rect'].right < 0: square['rect'].left = SCREEN_WIDTH
            if square['rect'].left > SCREEN_WIDTH: square['rect'].right = 0
            if square['rect'].bottom < 0: square['rect'].top = SCREEN_HEIGHT
            if square['rect'].top > SCREEN_HEIGHT: square['rect'].bottom = 0
            
            # Draw faint squares
            s = pygame.Surface((30, 30), pygame.SRCALPHA)
            s.fill(SQUARE_COLOR + (50,))
            screen.blit(s, square['rect'].topleft)

        # Draw Title
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, SCREEN_HEIGHT // 3))
        
        # Pulsing subtitle
        alpha = int(128 + 127 * math.sin(pygame.time.get_ticks() * 0.005))
        
        # Create a temporary surface to achieve the fade effect on text
        temp_surface = pygame.Surface(subtitle_text.get_size(), pygame.SRCALPHA)
        temp_surface.blit(subtitle_text, (0,0))
        temp_surface.set_alpha(alpha)
        
        screen.blit(temp_surface, (SCREEN_WIDTH // 2 - subtitle_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

        pygame.display.flip()
        clock.tick(FPS)

# --- Main Game Function ---
def game_loop(screen, clock, audio_assets):
    
    # Fonts
    ui_font = pygame.font.Font(None, 28)
    enemy_font = pygame.font.Font(None, 18) # Kept for consistency, though unused for text now
    go_font_big = pygame.font.Font(None, 72)

    # Unpack Audio Assets
    melody_tracks = audio_assets['melodies']
    bass_tracks = audio_assets['bass']
    shot_sound = audio_assets['shot']
    hit_sound = audio_assets['hit']
    death_sound = audio_assets['death']
    music_channel_melody = audio_assets['channel_melody']
    music_channel_bass = audio_assets['channel_bass']

    # Game state initialization
    game_active = True
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    enemies = [] # Contains Squares and Triangles
    rivals = []  # Contains RivalCircles
    bullets = [] # Player bullets
    rival_bullets = [] # Rival bullets
    items = []
    
    last_spawn_time = pygame.time.get_ticks()
    total_entities_spawned = 0
    spawn_cooldown = INITIAL_SPAWN_COOLDOWN
    current_music_index = -1

    # --- Game Loop Start ---
    while True:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if not game_active:
                 if event.type == pygame.KEYDOWN:
                     if event.key == pygame.K_r:
                        return # Restart the game loop

        # --- Music Management (Dynamic Intensity) ---
        if game_active:
            # Calculate intensity
            intensity = calculate_intensity(spawn_cooldown)
            
            # Select track based on intensity milestones
            num_tracks = len(melody_tracks)
            target_music_index = int(intensity * num_tracks)
            target_music_index = min(target_music_index, num_tracks - 1)

            # If the music needs to change, or if the current track finished (they are designed to loop)
            if target_music_index != current_music_index or not music_channel_melody.get_busy():
                current_music_index = target_music_index
                # Play both melody and bass simultaneously on separate channels
                music_channel_melody.play(melody_tracks[current_music_index])
                music_channel_bass.play(bass_tracks[current_music_index])

        
        if game_active:
            # --- Spawning Logic ---
            current_time = pygame.time.get_ticks()
            if current_time - last_spawn_time > spawn_cooldown:
                new_entity = spawn_entity(player.kills, total_entities_spawned)
                if isinstance(new_entity, RivalCircle):
                    rivals.append(new_entity)
                else:
                    enemies.append(new_entity)
                
                total_entities_spawned += 1
                last_spawn_time = current_time
                
                # Update spawn cooldown (Difficulty scaling)
                spawn_cooldown = max(MIN_SPAWN_COOLDOWN, INITIAL_SPAWN_COOLDOWN - player.kills * SPAWN_COOLDOWN_REDUCTION_PER_KILL)

            # --- Entity Updates ---
            
            # Player Update
            player.move()
            # Player shoots at both enemies and rivals
            player.shoot(enemies + rivals, bullets, shot_sound)
            
            # Item Collection
            for item in items[:]:
                if player.rect.colliderect(item.rect):
                    player.collect_item(item)
                    items.remove(item)

            # Enemy AI Update (Strategic Swarm)
            for enemy in enemies:
                enemy.strategic_move(player, enemies)
            
            # Rival AI Update (Strategic Positioning and Targeting)
            for rival in rivals: 
                rival.strategic_move(player, enemies)
                # Check if the target still exists (it might have been destroyed this frame)
                if rival.target and rival.target not in enemies:
                     rival.target = None
                rival.shoot(rival_bullets, shot_sound)
            
            # Bullet Updates
            for b in bullets + rival_bullets:
                b.move()
            
            # --- Collision Detection ---
            
            # Player Bullets (vs Enemies and Rivals)
            for bullet in bullets[:]:
                if bullet.is_offscreen():
                    if bullet in bullets: bullets.remove(bullet)
                    continue
                
                all_targets = enemies + rivals
                for target in all_targets[:]:
                    # Ensure target still exists before checking collision
                    if target in all_targets and bullet.rect.colliderect(target.rect):
                        pygame.mixer.find_channel(True).play(hit_sound)
                        
                        # Apply damage
                        if target.take_damage(bullet.damage):
                            # Handle Death
                            player.kills += 1
                            pygame.mixer.find_channel(True).play(death_sound)
                            
                            # Item Drop (if close enough to player)
                            if math.hypot(player.x - target.x, player.y - target.y) <= player.item_drop_range:
                                items.append(Item(target.x, target.y, player.kills))
                            
                            # Handle splitting (e.g., Triangles)
                            new_enemies = target.on_death()
                            enemies.extend(new_enemies)
                            
                            # Remove the target from the correct list
                            if isinstance(target, RivalCircle):
                                if target in rivals: rivals.remove(target)
                            else:
                                if target in enemies: enemies.remove(target)
                        
                        # Remove the bullet
                        if bullet in bullets: bullets.remove(bullet)
                        break # Bullet destroyed, move to next bullet

            # Rival Bullets (vs Enemies and Player)
            for bullet in rival_bullets[:]:
                if bullet.is_offscreen():
                    if bullet in rival_bullets: rival_bullets.remove(bullet)
                    continue
                
                # Check against Player (Game Over condition)
                if bullet.rect.colliderect(player.rect):
                    game_active = False
                    music_channel_melody.stop()
                    music_channel_bass.stop()
                    if bullet in rival_bullets: rival_bullets.remove(bullet)
                    continue

                # Check against Enemies
                for enemy in enemies[:]:
                     if enemy in enemies and bullet.rect.colliderect(enemy.rect):
                        pygame.mixer.find_channel(True).play(hit_sound)
                        
                        # Rival bullets do 1 damage
                        if enemy.take_damage(1):
                            # Handle splitting
                            new_splits = enemy.on_death()
                            enemies.extend(new_splits)
                            # Remove the enemy
                            if enemy in enemies: enemies.remove(enemy)
                        
                        # Remove the bullet
                        if bullet in rival_bullets: rival_bullets.remove(bullet)
                        break

            
            # Physical Collision (Player vs Enemies/Rivals) (Game Over condition)
            for unit in enemies + rivals:
                if player.rect.colliderect(unit.rect):
                    game_active = False
                    music_channel_melody.stop()
                    music_channel_bass.stop()
                    break

            # Physical Collision (Rivals vs Enemies) - Mutual Destruction
            for rival in rivals[:]:
                if rival not in rivals: continue # Ensure rival wasn't already destroyed this frame
                
                for enemy in enemies[:]:
                    if enemy not in enemies: continue # Ensure enemy wasn't already destroyed
                    
                    if rival.rect.colliderect(enemy.rect):
                        # Mutual destruction
                        pygame.mixer.find_channel(True).play(death_sound)
                        
                        # Handle potential triangle splitting
                        new_splits = enemy.on_death()
                        enemies.extend(new_splits)

                        # Remove both
                        if rival in rivals: rivals.remove(rival)
                        if enemy in enemies: enemies.remove(enemy)
                        
                        break # This rival is gone, break inner loop

            # --- Drawing ---
            screen.fill(BACKGROUND_COLOR)
            
            # Draw entities in order (Items -> Enemies -> Rivals -> Player -> Bullets)
            for item in items:
                item.draw(screen, ui_font)
            for enemy in enemies:
                enemy.draw(screen, enemy_font)
            for rival in rivals:
                rival.draw(screen, enemy_font)
                
            player.draw(screen)
            
            for b in bullets + rival_bullets:
                b.draw(screen)
                
            draw_ui(screen, player, ui_font, spawn_cooldown)
            
        else:
            # Game Over State
            draw_game_over(screen, player.kills, ui_font, go_font_big)

        # Update the display
        pygame.display.flip()
        # Cap the frame rate
        clock.tick(FPS)

def initialize_audio():
    # Initialize Mixer
    # Using a smaller buffer (512) can reduce audio latency
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16) # Allow enough channels for effects and music

    # Define Music (Improved structure, richer sound)
    # Notes (C Minor scale for a more dramatic feel)
    notes = {
        'C3': 130.81, 'D3': 146.83, 'Eb3': 155.56, 'F3': 174.61, 'G3': 196.00, 'Ab3': 207.65, 'Bb3': 233.08,
        'C4': 261.63, 'D4': 293.66, 'Eb4': 311.13, 'F4': 349.23, 'G4': 392.00, 'Ab4': 415.30, 'Bb4': 466.16,
        'C5': 523.25, 'D5': 587.33, 'Eb5': 622.25, 'F5': 698.46
    }
    # Note durations (Eighth note, Quarter note, Half note)
    en = 0.15; qn = 0.30; hn = 0.60

    # Defining 4 distinct musical segments that evolve in complexity based on game intensity
    # Segment 1 (Low Intensity)
    melody1 = [
        (notes['C4'], qn), (notes['Eb4'], qn), (notes['G4'], qn), (notes['Ab4'], en), (notes['G4'], en),
        (notes['F4'], hn), (notes['Eb4'], hn)
    ]
    bass1 = [
        (notes['C3'], hn), (notes['C3'], hn),
        (notes['F3'], hn), (notes['Ab3'], hn)
    ]

    # Segment 2 (Medium Intensity - Faster Arpeggios)
    melody2 = [
        (notes['C4'],en),(notes['Eb4'],en),(notes['G4'],en),(notes['C5'],en), (notes['C4'],en),(notes['Eb4'],en),(notes['G4'],en),(notes['C5'],en),
        (notes['Bb3'],en),(notes['D4'],en),(notes['F4'],en),(notes['Bb4'],en), (notes['Bb3'],en),(notes['D4'],en),(notes['F4'],en),(notes['Bb4'],en)
    ]
    bass2 = [
        (notes['C3'], qn), (notes['G3'], qn), (notes['C3'], qn), (notes['G3'], qn),
        (notes['Bb3'], qn), (notes['F3'], qn), (notes['Bb3'], qn), (notes['F3'], qn)
    ]

    # Segment 3 (High Intensity - More melodic movement)
    melody3 = [
        (notes['G4'], qn), (notes['Ab4'], en), (notes['Bb4'], en), (notes['C5'], qn), (notes['Bb4'], en), (notes['Ab4'], en),
        (notes['G4'], qn), (notes['F4'], qn), (notes['Eb4'], qn), (notes['D4'], qn)
    ]
    bass3 = [
       (notes['Eb3'], hn), (notes['F3'], hn),
       (notes['G3'], hn), (notes['Bb3'], hn)
    ]

    # Segment 4 (Max Intensity - High notes and fast rhythm)
    melody4 = [
       (notes['C5'],en),(notes['Eb5'],en),(notes['C5'],en),(notes['Ab4'],en), (notes['G4'],en),(notes['F4'],en),(notes['G4'],en),(notes['Ab4'],en),
       (notes['Bb4'],en),(notes['D5'],en),(notes['Bb4'],en),(notes['G4'],en), (notes['F4'],en),(notes['Eb4'],en),(notes['F4'],en),(notes['G4'],en)
    ]
    bass4 = [
        (notes['C3'], en), (notes['C3'], en), (notes['C3'], en), (notes['C3'], en), (notes['F3'], en), (notes['F3'], en), (notes['F3'], en), (notes['F3'], en),
        (notes['G3'], en), (notes['G3'], en), (notes['G3'], en), (notes['G3'], en), (notes['Ab3'], en), (notes['Ab3'], en), (notes['Ab3'], en), (notes['Ab3'], en)
    ]

    # Generate the sound objects
    melody_tracks = [generate_full_melody_sound(m, wave_type='sine') for m in [melody1, melody2, melody3, melody4]]
    bass_tracks = [generate_bass_track(b, wave_type='soft_square') for b in [bass1, bass2, bass3, bass4]]
    
    # Generate Sound Effects (Softer)
    shot_sound = generate_laser_sound()
    
    hit_sound_array = generate_sound_array(300, 0.05, wave_type='sine', amplitude=0.4)
    hit_sound = pygame.sndarray.make_sound(np.ascontiguousarray(np.vstack((hit_sound_array, hit_sound_array)).T))
    
    # Using the 'noise' approximation defined earlier
    death_sound_array = generate_sound_array(80, 0.2, wave_type='noise', amplitude=0.5)
    death_sound = pygame.sndarray.make_sound(np.ascontiguousarray(np.vstack((death_sound_array, death_sound_array)).T))
    
    # Reserve specific channels for music
    music_channel_melody = pygame.mixer.Channel(0)
    music_channel_bass = pygame.mixer.Channel(1)

    return {
        'melodies': melody_tracks,
        'bass': bass_tracks,
        'shot': shot_sound,
        'hit': hit_sound,
        'death': death_sound,
        'channel_melody': music_channel_melody,
        'channel_bass': music_channel_bass
    }


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("MADNESS")
    clock = pygame.time.Clock()

    # Initialize and load/generate audio assets
    print("Generating Audio Assets...")
    try:
        audio_assets = initialize_audio()
        print("Audio Ready.")
    except Exception as e:
        print(f"Failed to initialize audio: {e}. Running without sound.")
        # Provide dummy audio assets if initialization fails to prevent crashes
        class DummySound:
            def play(self, *args, **kwargs): pass
            def stop(self, *args, **kwargs): pass
            def get_busy(self): return False
        
        dummy = DummySound()
        # Dummy channels that won't actually play sound but will respond to API calls
        class DummyChannel:
             def play(self, *args, **kwargs): pass
             def stop(self, *args, **kwargs): pass
             def get_busy(self): return False

        audio_assets = {
            'melodies': [dummy], 'bass': [dummy], 'shot': dummy, 'hit': dummy, 'death': dummy,
            'channel_melody': DummyChannel(), 'channel_bass': DummyChannel()
        }


    # Start with the title screen
    title_screen(screen, clock)

    # Main game loop (restarts automatically)
    while True:
        game_loop(screen, clock, audio_assets)
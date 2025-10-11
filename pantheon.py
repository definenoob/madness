import sys
import math
import random

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    Vec3, Point3, LColor, Material,
    AmbientLight, DirectionalLight,
    NodePath, TextNode,
    GeomVertexFormat, GeomVertexData, Geom, GeomTriangles, GeomPoints, GeomNode, GeomVertexWriter,
    LineSegs, Quat,
    RenderModeAttrib
)
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task

# --- Configuration & Constants ---
STARTING_WORLD_RADIUS = 350.0
MIN_WORLD_RADIUS = 50.0
WORLD_SHRINK_SPEED = 0.5

# Time Dilation Settings
STARTING_ROCKETS = 100
MIN_TIME_DILATOR = 0.5
MAX_TIME_DILATOR = 1.0

# Rocket Settings
ROCKET_FORWARD_SPEED = 45.0
ROCKET_TURN_SPEED = 55.0
TURN_RADIUS_DECREASE_PER_KILL = 0.05
TURN_PENALTY_ON_MISS = 0.01 # Every missed shot increases turn radius
MIN_SPAWN_SEPARATION = 15.0

# Combat Settings
ROCKET_HITBOX_RADIUS = 0.75
ROCKET_BODY_RADIUS = 0.75
BULLET_RADIUS = 0.5
BULLET_SPEED = 90.0
BULLET_LIFETIME = 1.0 # This is now the fixed lifetime for all bullets
SHOOT_COOLDOWN = 0.6

# AI Settings
AI_OPTIMAL_DISTANCE = 60.0
AI_SHOOT_RANGE = 90.0
# Pathfinding constants
AI_PATHFINDING_RADIUS = 75.0 # How far the AI "looks" for bullets to pathfind around
AI_PATHFINDING_LEAD_TIME = 0.75 # How far ahead in time it projects its path
AI_FEELER_ANGLE = 30.0 # Angle of the pathfinding "feelers"
# Evasion constants
AI_TAIL_AWARENESS_RADIUS = 70.0
AI_TAIL_DOT_THRESHOLD = -0.9 # How directly behind a pursuer must be
AI_TAIL_AIM_THRESHOLD = 0.95 # How accurately the pursuer must be aiming
AI_OPPORTUNISTIC_SHOT_THRESHOLD = 0.98 # How accurately the AI must be aiming for a potshot
# Targeting constants
AI_PRIORITY_DISTANCE_WEIGHT = 0.8
AI_PRIORITY_KILLS_WEIGHT = 0.25
### NEW ###
# Desperation move constants
AI_SURROUNDED_RADIUS = 60.0 # Distance to check for nearby enemies
AI_SURROUNDED_THRESHOLD = 3  # Number of enemies to trigger panic
AI_PANIC_SPIN_SPEED = 120.0  # How fast it spins during the move
AI_PANIC_DURATION_MIN = 1.0  # Minimum duration of the panic state in seconds
AI_PANIC_DURATION_MAX = 2.5  # Maximum duration of the panic state in seconds


# Camera Settings
CAMERA_CHASE_SPEED = 4.0
DEFAULT_ZOOM = 50.0
MIN_ZOOM = 100.0
MAX_ZOOM = 1000.0
ZOOM_SPEED = 150.0

# Colors
BACKGROUND_COLOR = LColor(0.08, 0.08, 0.12, 1)
PLAYER_COLOR = LColor(0.1, 0.6, 1.0, 1)
ENEMY_COLOR = LColor(1, 0.2, 0.2, 1)
BULLET_COLOR = LColor(1.0, 0.8, 0.5, 1)
HITBOX_COLOR = LColor(1, 0.75, 0.05, 1)
TEXT_COLOR = LColor(0.94, 0.94, 0.94, 1)
WIN_COLOR = LColor(0.2, 1.0, 0.6, 1)


# --- CPU BULLET CLASS ---
class Bullet:
    def __init__(self, pos, velocity, shooter, max_age):
        self.pos = pos
        self.velocity = velocity
        self.shooter = shooter
        self.age = 0.0
        self.is_active = True
        self.max_age = max_age

# --- Procedural Geometry Functions ---
def create_cone(segments=16, height=2.0, radius=0.7):
    format = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData('cone', format, Geom.UHStatic)
    vwriter, nwriter = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'normal')
    apex, base_center = Point3(0, height / 2, 0), Point3(0, -height / 2, 0)
    vwriter.addData3f(apex); nwriter.addData3f(Vec3(0, 1, 0).normalized())
    vwriter.addData3f(base_center); nwriter.addData3f(Vec3(0, -1, 0))
    for i in range(segments):
        angle = (i / segments) * 2 * math.pi
        x, z = math.cos(angle) * radius, math.sin(angle) * radius
        vwriter.addData3f(x, -height / 2, z); nwriter.addData3f(Vec3(x, radius, z).normalized())
        vwriter.addData3f(x, -height / 2, z); nwriter.addData3f(0, -1, 0)
    prim = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        idx0, idx1 = 2 + i * 2, 2 + ((i + 1) % segments) * 2
        prim.addVertices(0, idx1, idx0)
        prim.addVertices(1, idx0 + 1, idx1 + 1)
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode('cone_geom'); node.addGeom(geom)
    return NodePath(node)

def create_icosphere(subdivisions=2):
    format = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData('sphere', format, Geom.UHStatic)
    vertex_writer, normal_writer = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'normal')
    vertices, triangles = [], []
    t = (1.0 + math.sqrt(5.0)) / 2.0
    def add_vertex(v): vertices.append(v.normalized()); return len(vertices) - 1
    add_vertex(Vec3(-1, t, 0)); add_vertex(Vec3(1, t, 0)); add_vertex(Vec3(-1, -t, 0)); add_vertex(Vec3(1, -t, 0))
    add_vertex(Vec3(0, -1, t)); add_vertex(Vec3(0, 1, t)); add_vertex(Vec3(0, -1, -t)); add_vertex(Vec3(0, 1, -t))
    add_vertex(Vec3(t, 0, -1)); add_vertex(Vec3(t, 0, 1)); add_vertex(Vec3(-t, 0, -1)); add_vertex(Vec3(-t, 0, 1))
    triangles = [(0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),(1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),
                 (3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),(4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)]
    midpoint_cache = {}
    def get_midpoint(p1, p2):
        key = tuple(sorted((p1, p2)))
        if key in midpoint_cache: return midpoint_cache[key]
        midpoint_index = add_vertex((vertices[p1] + vertices[p2]) / 2.0)
        midpoint_cache[key] = midpoint_index
        return midpoint_index
    for _ in range(subdivisions):
        new_triangles = []
        for tri in triangles:
            v1, v2, v3 = tri
            a, b, c = get_midpoint(v1, v2), get_midpoint(v2, v3), get_midpoint(v3, v1)
            new_triangles.extend([(v1,a,c), (v2,b,a), (v3,c,b), (a,b,c)])
        triangles = new_triangles
    for v in vertices: vertex_writer.addData3f(v); normal_writer.addData3f(v)
    prim = GeomTriangles(Geom.UHStatic)
    for tri in triangles:
        prim.addVertices(tri[0], tri[1], tri[2])
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode('sphere_geom'); node.addGeom(geom)
    return NodePath(node)

# --- Helper Functions ---
def normalized_vector(v):
    return v.normalized() if v.length_squared() > 1e-6 else Vec3(0)

# --- Game Classes ---
class Rocket(NodePath):
    def __init__(self, game, pos, is_player=False):
        super().__init__("Rocket")
        self.game = game
        self.is_player = is_player
        self.is_active = True
        self.kills = 0

        color = PLAYER_COLOR if self.is_player else ENEMY_COLOR
        
        scale = Vec3(1.5, 2.5, 1.5)
        self.model = create_cone()
        self.model.reparentTo(self)
        self.model.setColor(color)
        mat = Material(); mat.setAmbient(color*0.5); mat.setDiffuse(color*0.9); mat.setEmission(color*0.2)
        self.model.setMaterial(mat, 1)
        self.setScale(scale)
        self.setPos(pos)

        self.speed = ROCKET_FORWARD_SPEED
        self.base_turn_speed = ROCKET_TURN_SPEED
        self.current_turn_speed = self.base_turn_speed
        self._last_forward = self.calculate_initial_forward()
        self.velocity = self._last_forward * self.speed
        self.shoot_timer = 0.0
        self.target = None
        self.look_at_sphere_surface()

        # State for tail evasion maneuver
        self.evasion_timer = 0.0
        self.evade_dir = 1
        
        ### NEW ###
        # State for desperation move
        self.panic_timer = 0.0

        self.hitbox_collision_pos = Point3(0, -1.0, 0)
        hitbox_model = create_icosphere(1)
        hitbox_model.reparentTo(self)
        hitbox_model.setPos(self.hitbox_collision_pos)
        hitbox_model.setScale(
            ROCKET_HITBOX_RADIUS / self.getScale().x,
            ROCKET_HITBOX_RADIUS / self.getScale().y,
            ROCKET_HITBOX_RADIUS / self.getScale().z
        )
        hitbox_model.setColor(HITBOX_COLOR)
        hitbox_mat = Material(); hitbox_mat.setEmission(HITBOX_COLOR * 0.8)
        hitbox_model.setMaterial(hitbox_mat, 1); hitbox_model.setLightOff()

    def register_kill(self):
        self.kills += 1
        if TURN_RADIUS_DECREASE_PER_KILL < 1.0:
            self.current_turn_speed *= (1 / (1 - TURN_RADIUS_DECREASE_PER_KILL))
        self.speed *= 1.05
        self.velocity = normalized_vector(self.velocity) * self.speed

    def calculate_initial_forward(self):
        up = normalized_vector(self.getPos())
        ref = Vec3(0, 1, 0)
        if abs(up.dot(ref)) > 0.99: ref = Vec3(1, 0, 0)
        return normalized_vector(ref.cross(up))

    def look_at_sphere_surface(self, forward_vector=None):
        up = normalized_vector(self.getPos())
        if forward_vector is None:
            forward_vector = self._last_forward if self.velocity.length_squared() < 1e-6 else normalized_vector(self.velocity)
        forward_vector = (forward_vector - up * forward_vector.dot(up)).normalized()
        if forward_vector.length_squared() < 1e-6:
            forward_vector = self.calculate_initial_forward()
        self._last_forward = forward_vector
        self.lookAt(self.getPos() + forward_vector, up)

    def update(self, dt):
        if self.velocity.length_squared() > 0:
            new_pos = self.getPos() + self.velocity * dt
            new_pos_norm = normalized_vector(new_pos)
            self.setPos(new_pos_norm * self.game.current_world_radius)
            self.velocity -= new_pos_norm * self.velocity.dot(new_pos_norm)
        self.look_at_sphere_surface()
        if self.shoot_timer > 0: self.shoot_timer -= dt

    def shoot(self):
        if self.shoot_timer <= 0:
            self.shoot_timer = SHOOT_COOLDOWN
            spawn_pos = self.getPos() + self._last_forward * 4.0
            self.game.spawn_bullet(spawn_pos, self._last_forward, self)
            
            # Apply all penalties instantly on firing
            self.speed *= 0.99
            self.velocity = normalized_vector(self.velocity) * self.speed
            self.current_turn_speed *= (1.0 - TURN_PENALTY_ON_MISS)

    def control(self, dt):
        key_map = self.game.key_map
        turn_value = key_map.get("d", 0) - key_map.get("a", 0)
        if turn_value != 0:
            up = normalized_vector(self.getPos())
            forward = normalized_vector(self.velocity)
            right = forward.cross(up)
            turn_force = right * turn_value * self.current_turn_speed
            self.velocity = normalized_vector(self.velocity + turn_force * dt) * self.speed
        if key_map.get("space", 0): self.shoot()

    def select_target(self, all_other_rockets):
        best_target = None
        highest_priority = -1.0
        my_pos = self.getPos()
        if not all_other_rockets: return None
        for r in all_other_rockets:
            if not r.is_active: continue
            dist = (my_pos - r.getPos()).length()
            priority = AI_PRIORITY_DISTANCE_WEIGHT * (1.0 / (dist + 1.0))
            priority *= (1.0 + r.kills * AI_PRIORITY_KILLS_WEIGHT)
            if priority > highest_priority:
                highest_priority = priority
                best_target = r
        return best_target

    def evaluate_path_danger(self, path_dir, all_bullets):
        danger = 0.0
        projected_pos = self.getPos() + path_dir * self.speed * AI_PATHFINDING_LEAD_TIME
        
        for bullet in all_bullets:
            if not bullet.is_active or bullet.shooter == self:
                continue

            vec_to_path = projected_pos - bullet.pos
            dist_sq = vec_to_path.length_squared()

            if dist_sq < AI_PATHFINDING_RADIUS ** 2:
                threat = 1.0 / (dist_sq + 1.0)
                dir_to_path = normalized_vector(vec_to_path)
                bullet_dir = normalized_vector(bullet.velocity)
                dot = bullet_dir.dot(dir_to_path)

                if dot > 0:
                    threat *= (1 + dot * 2)

                danger += threat
        return danger

    def update_ai(self, dt, all_other_rockets, all_bullets):
        my_pos = self.getPos()
        my_forward = normalized_vector(self.velocity)
        up = normalized_vector(my_pos)
        right = my_forward.cross(up)
        
        ### NEW ###
        # --- 1. Highest Priority: Desperation Spin-and-Shoot ---
        if self.panic_timer > 0:
            self.panic_timer -= dt
            # Spin rapidly in a random direction (chosen once at the start of panic)
            turn_force = right * self.evade_dir * AI_PANIC_SPIN_SPEED
            self.velocity = normalized_vector(self.velocity + turn_force * dt) * self.speed
            # Shoot as fast as possible
            self.shoot()
            return # Skip all other logic

        # Check if we should ENTER the panic state
        surrounded_count = 0
        for r in all_other_rockets:
            if (r.getPos() - my_pos).length_squared() < AI_SURROUNDED_RADIUS ** 2:
                surrounded_count += 1
        
        if surrounded_count >= AI_SURROUNDED_THRESHOLD:
            self.panic_timer = random.uniform(AI_PANIC_DURATION_MIN, AI_PANIC_DURATION_MAX)
            self.evade_dir = random.choice([-1, 1]) # Pick a spin direction
            return # End AI logic for this frame, panic will start next frame

        target_velocity_dir = None
        
        # --- 2. High Priority: Evade a tailing rocket ---
        tailing_rocket = None
        for r in all_other_rockets:
            vec_to_r = r.getPos() - my_pos
            dist_sq = vec_to_r.length_squared()

            if dist_sq < AI_TAIL_AWARENESS_RADIUS ** 2:
                if my_forward.dot(normalized_vector(r.getPos() - my_pos)) < AI_TAIL_DOT_THRESHOLD:
                    their_forward = normalized_vector(r.velocity)
                    vec_from_them_to_me = my_pos - r.getPos()
                    if their_forward.dot(normalized_vector(vec_from_them_to_me)) > AI_TAIL_AIM_THRESHOLD:
                        tailing_rocket = r
                        break

        if tailing_rocket:
            if self.evasion_timer <= 0:
                self.evasion_timer = random.uniform(0.5, 1.2)
                self.evade_dir = random.choice([-1, 1])
            target_velocity_dir = right * self.evade_dir
            self.evasion_timer -= dt
        
        # --- 3. Medium Priority: Pathfind through bullets ---
        if target_velocity_dir is None:
            self.evasion_timer = 0
            q = Quat()
            q.setFromAxisAngle(AI_FEELER_ANGLE, up)
            dir_left = q.xform(my_forward)
            
            q.setFromAxisAngle(-AI_FEELER_ANGLE, up)
            dir_right = q.xform(my_forward)

            danger_straight = self.evaluate_path_danger(my_forward, all_bullets)
            danger_left = self.evaluate_path_danger(dir_left, all_bullets)
            danger_right = self.evaluate_path_danger(dir_right, all_bullets)

            if danger_straight <= danger_left and danger_straight <= danger_right:
                target_velocity_dir = my_forward
            elif danger_left < danger_right:
                target_velocity_dir = dir_left
            else:
                target_velocity_dir = dir_right

        if target_velocity_dir is None:
             target_velocity_dir = my_forward

        # --- 4. Low Priority: Hunt a target ---
        if not self.target or not self.target.is_active or random.random() < 0.05:
            self.target = self.select_target(all_other_rockets)
        
        if self.target:
            target_pos = self.target.getPos()
            target_forward = normalized_vector(self.target.velocity) if self.target.velocity.length_squared() > 0 else self.target._last_forward
            tail_position = target_pos - target_forward * AI_OPTIMAL_DISTANCE
            dir_to_tail = (tail_position - my_pos)
            dir_to_tail_on_plane = (dir_to_tail - up * dir_to_tail.dot(up)).normalized()
            
            final_dir = (target_velocity_dir * 0.6 + dir_to_tail_on_plane * 0.4).normalized()
        else:
            final_dir = target_velocity_dir

        if final_dir.length_squared() > 0:
            self.velocity = normalized_vector(self.velocity + final_dir * self.current_turn_speed * dt) * self.speed
        
        # --- 5. Independent opportunistic shooting ---
        for potential_shot_target in all_other_rockets:
            if not potential_shot_target.is_active: continue
            dir_to_potential_target = normalized_vector(potential_shot_target.getPos() - my_pos)
            angle = my_forward.dot(dir_to_potential_target)
            dist_sq = (my_pos - potential_shot_target.getPos()).length_squared()

            if dist_sq < AI_SHOOT_RANGE ** 2 and angle > AI_OPPORTUNISTIC_SHOT_THRESHOLD:
                self.shoot()
                break 

    def destroy(self):
        self.is_active = False
        if not self.isEmpty(): self.removeNode()

# --- Main Game Application ---
class RocketSphere(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.setBackgroundColor(BACKGROUND_COLOR)
        self.setup_lights()
        self.setup_input()

        self.game_active = False
        self.ui_elements = {}
        self.player_ref = None
        self.all_rockets = []
        self.all_bullets = []
        
        self.zoom_level = MAX_ZOOM
        self.time_dilator = 1.0
        
        self.bullet_vdata = None
        self.bullet_geom_node = None
        
        self.current_world_radius = STARTING_WORLD_RADIUS

        self.show_title_screen()
        self.accept("escape", sys.exit)
        self.accept("r", self.restart_game)

    def setup_lights(self):
        ambient = AmbientLight("ambient"); ambient.setColor(LColor(0.5, 0.5, 0.6, 1))
        self.render.setLight(self.render.attachNewNode(ambient))
        dlight = DirectionalLight("dlight"); dlight.setColor(LColor(1.0, 0.95, 0.8, 1))
        dlnp = self.render.attachNewNode(dlight); dlnp.setHpr(45, -45, 0)
        self.render.setLight(dlnp)

    def setup_input(self):
        self.key_map = {}
        keys_to_map = ["a", "d", "w", "s", "space"]
        for key in keys_to_map:
            self.accept(key, self.set_key, [key, 1])
            self.accept(f"{key}-up", self.set_key, [key, 0])

    def setup_cpu_simulation(self):
        vformat = GeomVertexFormat.get_v3c4()
        self.bullet_vdata = GeomVertexData("bullets", vformat, Geom.UH_dynamic)
        prim = GeomPoints(Geom.UH_static)
        geom = Geom(self.bullet_vdata)
        geom.addPrimitive(prim)
        node = GeomNode('bullet_geom')
        node.addGeom(geom)
        self.bullet_geom_node = self.render.attachNewNode(node)
        self.bullet_geom_node.set_render_mode_thickness(5)
        self.bullet_geom_node.set_attrib(RenderModeAttrib.make(RenderModeAttrib.M_point))
        self.bullet_geom_node.setLightOff()
        self.bullet_geom_node.setColor(BULLET_COLOR)


    def set_key(self, key, value):
        self.key_map[key] = value

    def restart_game(self):
        self.taskMgr.remove("TitleScreenUpdate")
        if self.game_active: self.taskMgr.remove("GameLoop")
        self.start_game()

    def generate_spawn_points(self, num_points):
        points = []
        phi = math.pi * (3. - math.sqrt(5.))
        for i in range(num_points):
            y = 1 - (i / float(num_points - 1)) * 2
            radius = math.sqrt(1 - y * y)
            theta = phi * i
            x = math.cos(theta) * radius
            z = math.sin(theta) * radius
            points.append(Point3(x, y, z) * STARTING_WORLD_RADIUS)
        return points

    def start_game(self):
        self.cleanup_game()
        self.clear_ui()
        self.current_world_radius = STARTING_WORLD_RADIUS
        self.create_world()
        self.setup_cpu_simulation()
        
        spawn_points = self.generate_spawn_points(STARTING_ROCKETS)
        random.shuffle(spawn_points)

        for i in range(STARTING_ROCKETS):
            is_player = (i == 0)
            pos = spawn_points.pop()
            rocket = Rocket(self, pos, is_player=is_player)
            self.all_rockets.append(rocket)
            if is_player:
                self.player_ref = rocket
            rocket.reparentTo(self.render)

        self.setup_camera()
        self.game_active = True
        self.taskMgr.add(self.game_loop, "GameLoop")

    def cleanup_game(self):
        for r in self.all_rockets: r.destroy()
        self.all_rockets, self.player_ref = [], None
        self.all_bullets = []
        if hasattr(self, 'world_sphere'): self.world_sphere.removeNode()
        if self.bullet_geom_node: self.bullet_geom_node.removeNode()
        self.bullet_geom_node = None
        self.bullet_vdata = None

    def create_world(self):
        self.world_sphere = create_icosphere(subdivisions=5)
        self.world_sphere.setScale(self.current_world_radius)
        mat = Material(); base_color = LColor(0.1, 0.15, 0.3, 1)
        mat.setAmbient(base_color * 0.6); mat.setDiffuse(base_color * 0.9)
        self.world_sphere.setMaterial(mat, 1); self.world_sphere.reparentTo(self.render)
        self._create_world_grid().reparentTo(self.world_sphere)

    def _create_world_grid(self, num_lat=18, num_lon=36):
        ls = LineSegs("grid"); ls.setThickness(1.0); ls.setColor(0.2, 0.3, 0.6, 0.8)
        radius = 1.005
        # Latitude lines
        for i in range(1, num_lat):
            lat = math.pi * i / num_lat - math.pi / 2
            r = radius * math.cos(lat)
            z = radius * math.sin(lat)
            for j in range(num_lon + 1):
                lon = 2 * math.pi * j / num_lon
                x = r * math.cos(lon)
                y = r * math.sin(lon)
                if j == 0: ls.moveTo(x, y, z)
                else: ls.drawTo(x, y, z)
        # Longitude lines
        for i in range(num_lon):
            lon = 2 * math.pi * i / num_lon
            for j in range(num_lat + 1):
                lat = math.pi * j / num_lat - math.pi / 2
                r = radius * math.cos(lat)
                z = radius * math.sin(lat)
                x = r * math.cos(lon)
                y = r * math.sin(lon)
                if j == 0: ls.moveTo(x, y, z)
                else: ls.drawTo(x, y, z)
        node = NodePath(ls.create()); node.setLightOff(); return node

    def setup_camera(self):
        self.disableMouse()
        if self.player_ref:
            self.camera.setPos(self.player_ref.getPos() + normalized_vector(self.player_ref.getPos()) * self.zoom_level)
            self.update_camera(0.1)

    def handle_zoom(self, dt):
        zoom_input = self.key_map.get("s", 0) - self.key_map.get("w", 0)
        self.zoom_level += zoom_input * ZOOM_SPEED * dt
        self.zoom_level = max(MIN_ZOOM, min(self.zoom_level, MAX_ZOOM))

    def update_camera(self, dt):
        if not self.player_ref or not self.player_ref.is_active: return
        rocket_pos = self.player_ref.getPos()
        up_vec = normalized_vector(rocket_pos)
        target_pos = rocket_pos + up_vec * self.zoom_level
        current_pos = self.camera.getPos()
        interp_factor = 1.0 - math.exp(-dt * CAMERA_CHASE_SPEED)
        new_pos = current_pos + (target_pos - current_pos) * interp_factor
        self.camera.setPos(new_pos)
        forward_vec = normalized_vector(self.player_ref.velocity) or self.player_ref._last_forward
        self.camera.lookAt(self.player_ref.getPos(), forward_vec)

    def update_time_dilator(self):
        start_count = STARTING_ROCKETS; end_count = 2
        rocket_range = float(start_count - end_count)
        if rocket_range <= 0: self.time_dilator = 1.0; return
        current_rockets = len(self.all_rockets)
        progress = (start_count - current_rockets) / rocket_range
        progress = max(0.0, min(1.0, progress))
        eased_progress = progress ** 2
        time_range = MAX_TIME_DILATOR - MIN_TIME_DILATOR
        self.time_dilator = MIN_TIME_DILATOR + (eased_progress * time_range)

    def update_bullets_cpu(self, dt):
        rockets_to_destroy = set()
        for bullet in self.all_bullets:
            if not bullet.is_active: continue
            bullet.age += dt
            if bullet.age > bullet.max_age:
                bullet.is_active = False
                continue
            new_pos = bullet.pos + bullet.velocity * dt
            new_pos_norm = normalized_vector(new_pos)
            bullet.pos = new_pos_norm * self.current_world_radius
            bullet.velocity -= new_pos_norm * bullet.velocity.dot(new_pos_norm)
            for rocket in self.all_rockets:
                if not rocket.is_active or rocket == bullet.shooter: continue
                pA_local = Point3(0, 2.5, 0)
                pB_local = Point3(0, -2.5, 0)
                pA_world = self.render.getRelativePoint(rocket, pA_local)
                pB_world = self.render.getRelativePoint(rocket, pB_local)
                segment_vec = pB_world - pA_world
                len_sq = segment_vec.length_squared()
                if len_sq == 0: closest_point_on_segment = pA_world
                else:
                    bullet_vec = bullet.pos - pA_world
                    t = max(0, min(1, segment_vec.dot(bullet_vec) / len_sq))
                    closest_point_on_segment = pA_world + segment_vec * t
                dist_sq = (bullet.pos - closest_point_on_segment).length_squared()
                min_dist = ROCKET_BODY_RADIUS + BULLET_RADIUS
                if dist_sq < min_dist * min_dist:
                    rockets_to_destroy.add(rocket)
                    bullet.is_active = False
                    if bullet.shooter and bullet.shooter.is_active:
                        bullet.shooter.register_kill()
                    break
        self.all_bullets = [b for b in self.all_bullets if b.is_active]
        for rocket in rockets_to_destroy:
            rocket.is_active = False

    def update_bullet_geom(self):
        if not self.bullet_geom_node or self.bullet_geom_node.is_empty(): return
        vdata = self.bullet_geom_node.node().modifyGeom(0).modifyVertexData()
        vdata.setNumRows(len(self.all_bullets))
        vertex_writer = GeomVertexWriter(vdata, 'vertex')
        color_writer = GeomVertexWriter(vdata, 'color')
        for bullet in self.all_bullets:
            vertex_writer.setData3(bullet.pos)
            color_writer.setData4(BULLET_COLOR)
        prim = self.bullet_geom_node.node().modifyGeom(0).modifyPrimitive(0)
        prim.clearVertices()
        prim.addConsecutiveVertices(0, len(self.all_bullets))

    def update_world_shrink(self, dt):
        rocket_range = float(STARTING_ROCKETS - 2)
        if rocket_range <= 0: target_radius = MIN_WORLD_RADIUS
        else:
            progress = max(0.0, min(1.0, (len(self.all_rockets) - 2) / rocket_range))
            radius_range = STARTING_WORLD_RADIUS - MIN_WORLD_RADIUS
            target_radius = MIN_WORLD_RADIUS + (progress * radius_range)
        interp_factor = 1.0 - math.exp(-dt * WORLD_SHRINK_SPEED)
        self.current_world_radius += (target_radius - self.current_world_radius) * interp_factor
        self.world_sphere.setScale(self.current_world_radius)
        
    def game_loop(self, task):
        if not self.game_active: return Task.done
        self.update_time_dilator()
        self.update_world_shrink(globalClock.getDt())
        
        dt = min(globalClock.getDt() * self.time_dilator, 1/30.0)
        
        for rocket in self.all_rockets:
            if rocket.is_player:
                rocket.control(dt)
            else:
                other_rockets = [r for r in self.all_rockets if r != rocket and r.is_active]
                rocket.update_ai(dt, other_rockets, self.all_bullets)
            
            rocket.update(dt)
        
        self.update_bullets_cpu(dt)
        self.update_bullet_geom()

        rockets_to_remove = [r for r in self.all_rockets if not r.is_active]
        if rockets_to_remove:
            self.all_rockets = [r for r in self.all_rockets if r.is_active]
            for r in rockets_to_remove: r.destroy()
            
        self.handle_zoom(dt)
        self.update_camera(dt)
        self.update_game_ui()
        
        if self.game_active:
            is_player_alive = self.player_ref and self.player_ref.is_active
            if not is_player_alive: self.handle_game_over()
            elif len(self.all_rockets) == 1 and self.all_rockets[0].is_player: self.handle_game_won()
            
        return Task.cont

    def spawn_bullet(self, pos, direction, shooter):
        vel = direction * BULLET_SPEED
        max_age = BULLET_LIFETIME 
        bullet = Bullet(pos, vel, shooter, max_age)
        self.all_bullets.append(bullet)

    def handle_game_over(self):
        if not self.game_active: return
        self.game_active = False; self.taskMgr.remove("GameLoop"); self.player_ref = None
        self.update_ui_text("GameOver", "GAME OVER", (0, 0.1), 0.15, align=TextNode.ACenter, color=ENEMY_COLOR)
        self.update_ui_text("RestartPrompt", "Press R to Restart", (0, -0.1), 0.07)

    def handle_game_won(self):
        if not self.game_active: return
        self.game_active = False; self.taskMgr.remove("GameLoop")
        self.update_ui_text("GameWon", "YOU ARE THE LAST ONE STANDING", (0, 0.1), 0.1, align=TextNode.ACenter, color=WIN_COLOR)
        self.update_ui_text("RestartPrompt", "Press R to Play Again", (0, -0.1), 0.07)

    def update_game_ui(self):
        if not self.game_active: return
        is_player_alive = self.player_ref and self.player_ref.is_active
        health_text = f"Hull Integrity: {'100%' if is_player_alive else 'BREACHED'}"
        rockets_left_text = f"Rockets Left: {len(self.all_rockets)}"
        
        player_speed = self.player_ref.speed if is_player_alive else 0
        speed_text = f"Speed: {player_speed:.1f}"
        
        player_turn_speed = self.player_ref.current_turn_speed if is_player_alive else 0
        turn_speed_text = f"Turn: {player_turn_speed:.1f}"

        self.update_ui_text("Health", health_text, (-1.3, 0.9), 0.05, align=TextNode.ALeft)
        self.update_ui_text("Enemies", rockets_left_text, (1.3, 0.9), 0.05, align=TextNode.ARight)
        self.update_ui_text("PlayerSpeed", speed_text, (-1.3, -0.9), 0.05, align=TextNode.ALeft)
        self.update_ui_text("TurnSpeed", turn_speed_text, (1.3, -0.9), 0.05, align=TextNode.ARight)


    def show_title_screen(self):
        self.clear_ui()
        self.update_ui_text("Title", "ROCKET SPHERE", (0, 0.5), 0.12)
        self.update_ui_text("StartPrompt", "Press R to Start\nA/D to Steer | W/S to Zoom\nSpace to Shoot", (0, 0.2), 0.07)
        self.current_world_radius = STARTING_WORLD_RADIUS
        self.create_world()
        self.camera.setPos(0, -STARTING_WORLD_RADIUS * 3, STARTING_WORLD_RADIUS * 1.5); self.camera.lookAt(0, 0, 0)
        self.taskMgr.add(self.title_screen_update, "TitleScreenUpdate")

    def title_screen_update(self, task):
        if self.game_active: return Task.done
        if hasattr(self, 'world_sphere'): self.world_sphere.setH(self.world_sphere.getH() + globalClock.getDt() * 5)
        return Task.cont

    def update_ui_text(self, key, text, pos, scale=0.05, align=TextNode.ACenter, color=TEXT_COLOR):
        if key in self.ui_elements:
            self.ui_elements[key].setText(text); self.ui_elements[key].setFg(color)
        else: self.ui_elements[key] = OnscreenText(text=text, pos=pos, scale=scale, fg=color, align=align, mayChange=True, parent=self.aspect2d)

    def clear_ui(self):
        for e in self.ui_elements.values(): e.destroy()
        self.ui_elements.clear()

if __name__ == "__main__":
    print("Initializing Rocket Sphere...")
    app = RocketSphere()
    app.run()

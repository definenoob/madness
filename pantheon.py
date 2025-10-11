import sys
import math
import random
import struct

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    Vec3, Point3, LColor, Material,
    AmbientLight, DirectionalLight,
    NodePath, TextNode, Shader,
    GeomVertexFormat, GeomVertexData, Geom, GeomTriangles, GeomPoints, GeomNode, GeomVertexWriter,
    LineSegs, CollisionNode, CollisionSphere, CollisionTraverser, CollisionHandlerEvent, BitMask32,
    Texture, PTA_float,
    RenderModeAttrib, ShaderAttrib
)
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task

# --- Configuration & Constants ---
WORLD_RADIUS = 500.0

# Time Dilation Settings
STARTING_ROCKETS = 100
MIN_TIME_DILATOR = 0.2
MAX_TIME_DILATOR = 2.0

# Rocket Settings
ROCKET_FORWARD_SPEED = 45.0
ROCKET_TURN_SPEED = 55.0
MIN_SPAWN_SEPARATION = 15.0 

# Combat Settings
ROCKET_HITBOX_RADIUS = 0.75 
BULLET_RADIUS = 0.5
BULLET_SPEED = 90.0
BULLET_LIFETIME = 2.0 

# AI Settings
AI_OPTIMAL_DISTANCE = 50.0
AI_EVASION_RADIUS = 30.0
AI_SHOOT_RANGE = 80.0
AI_DODGE_RADIUS = 25.0

# --- GPU ACCELERATION SETTINGS ---
MAX_BULLETS = 10000
COMPUTE_GROUP_SIZE = 128 # Must match local_size_x in compute shader
SHOOT_COOLDOWN = 0.2 

# Camera Settings
CAMERA_CHASE_SPEED = 4.0
DEFAULT_ZOOM = 50.0
MIN_ZOOM = 100.0
MAX_ZOOM = 300.0
ZOOM_SPEED = 150.0

# Collision Masks
ROCKET_MASK = BitMask32.bit(1)
BULLET_MASK = BitMask32.bit(2)

# Colors
BACKGROUND_COLOR = LColor(0.08, 0.08, 0.12, 1)
PLAYER_COLOR = LColor(0.1, 0.6, 1.0, 1)
ENEMY_COLOR = LColor(1, 0.2, 0.2, 1)
BULLET_COLOR = LColor(1.0, 0.8, 0.5, 1)
HITBOX_COLOR = LColor(1, 0.75, 0.05, 1)
TEXT_COLOR = LColor(0.94, 0.94, 0.94, 1)
WIN_COLOR = LColor(0.2, 1.0, 0.6, 1)


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
def distance_on_sphere(pos1, pos2):
    cos_theta = max(-1.0, min(1.0, normalized_vector(pos1).dot(normalized_vector(pos2))))
    return WORLD_RADIUS * math.acos(cos_theta)
def get_direction_on_sphere(start_pos, end_pos):
    plane_normal = start_pos.cross(end_pos)
    direction = plane_normal.cross(start_pos)
    return normalized_vector(direction)

# --- Game Classes ---
class Rocket(NodePath):

    def __init__(self, game, pos, is_player=False):
        super().__init__("Rocket")
        self.game = game
        self.is_player = is_player
        
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
        self.turn_speed = ROCKET_TURN_SPEED
        self._last_forward = self.calculate_initial_forward()
        self.velocity = self._last_forward * self.speed
        self.shoot_timer = 0.0
        self.target = None
        self.look_at_sphere_surface()
        
        # --- FIX IS HERE ---
        # Store the position as an instance attribute
        self.hitbox_collision_pos = Point3(0, -1.0, 0) 
        hitbox_model = create_icosphere(1)
        hitbox_model.reparentTo(self)
        # Use the new attribute here
        hitbox_model.setPos(self.hitbox_collision_pos)
        hitbox_model.setScale(
            ROCKET_HITBOX_RADIUS / self.getScale().x,
            ROCKET_HITBOX_RADIUS / self.getScale().y,
            ROCKET_HITBOX_RADIUS / self.getScale().z
        )
        hitbox_model.setColor(HITBOX_COLOR)
        hitbox_mat = Material(); hitbox_mat.setEmission(HITBOX_COLOR * 0.8)
        hitbox_model.setMaterial(hitbox_mat, 1); hitbox_model.setLightOff()

        self.c_np = self.attachNewNode(CollisionNode("Rocket"))
        # And use the new attribute here as well
        self.c_np.node().addSolid(CollisionSphere(self.hitbox_collision_pos, ROCKET_HITBOX_RADIUS))
        self.c_np.node().setFromCollideMask(ROCKET_MASK)
        self.c_np.node().setIntoCollideMask(ROCKET_MASK)
        if self.getScale().x != self.getScale().y or self.getScale().y != self.getScale().z:
            self.c_np.setScale(1/self.getScale().x, 1/self.getScale().y, 1/self.getScale().z)

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
            self.setPos(new_pos_norm * WORLD_RADIUS)
            self.velocity -= new_pos_norm * self.velocity.dot(new_pos_norm)
        self.look_at_sphere_surface()
        if self.shoot_timer > 0: self.shoot_timer -= dt
        
    def shoot(self):
        if self.shoot_timer <= 0:
            self.shoot_timer = SHOOT_COOLDOWN
            spawn_pos = self.getPos() + self._last_forward * 4.0
            self.game.spawn_bullet(spawn_pos, self._last_forward)

    def control(self, dt):
        key_map = self.game.key_map
        turn_value = key_map.get("d", 0) - key_map.get("a", 0)
        if turn_value != 0:
            up = normalized_vector(self.getPos())
            forward = normalized_vector(self.velocity)
            right = forward.cross(up)
            turn_force = right * turn_value * self.turn_speed
            self.velocity = normalized_vector(self.velocity + turn_force * dt) * self.speed
        if key_map.get("space", 0): self.shoot()

    def update_ai(self, dt, all_other_rockets):
        if not all_other_rockets: return
        self.target = min(all_other_rockets, key=lambda r: distance_on_sphere(self.getPos(), r.getPos()))
        
        dist_to_target = distance_on_sphere(self.getPos(), self.target.getPos())
        dir_to_target = get_direction_on_sphere(self.getPos(), self.target.getPos())
        
        target_velocity_dir = Vec3(0)
        if dist_to_target < AI_EVASION_RADIUS: target_velocity_dir = -dir_to_target
        elif dist_to_target > AI_OPTIMAL_DISTANCE: target_velocity_dir = dir_to_target
        else: target_velocity_dir = dir_to_target.cross(normalized_vector(self.getPos()))
        
        self.velocity = normalized_vector(self.velocity + target_velocity_dir * self.turn_speed * dt) * self.speed
        
        if dist_to_target < AI_SHOOT_RANGE: self.shoot()
        
    def destroy(self):
        if self.c_np: self.c_np.removeNode()
        if not self.isEmpty(): self.removeNode()

# --- Main Game Application ---
class RocketSphere(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.setBackgroundColor(BACKGROUND_COLOR)
        self.setup_lights()
        self.setup_input()
        
        self.cTrav = CollisionTraverser("traverser")
        self.coll_handler = CollisionHandlerEvent()
        self.setup_collisions()
        
        self.game_active = False
        self.ui_elements = {}
        self.player_ref = None 
        self.all_rockets = []
        self.zoom_level = DEFAULT_ZOOM
        self.time_dilator = 1.0

        self.compute_node = None
        self.rocket_buffer = None
        self.bullet_buffer = None
        self.bullet_node = None
        self.bullet_write_index = 0
        
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

    def setup_collisions(self):
        self.coll_handler.addInPattern('%fn-into-%in')
        self.accept('Rocket-into-Rocket', self.on_rocket_collision)

    def setup_gpu_acceleration(self):
        try:
            compute_shader = Shader.load_compute(Shader.SL_GLSL, "collision_compute.glsl")
            render_shader = Shader.load(Shader.SL_GLSL, vertex="bullet_vert.glsl", fragment="bullet_frag.glsl")
        except Exception as e:
            print(f"Error loading shaders: {e}")
            self.userExit()
            return
        
        rocket_struct_size = 32
        bullet_struct_size = 32
        
        self.rocket_buffer = Texture()
        self.rocket_buffer.setup_buffer_texture(STARTING_ROCKETS * rocket_struct_size, Texture.T_float, Texture.F_rgba32, Geom.UH_dynamic)
        
        self.bullet_buffer = Texture()
        self.bullet_buffer.setup_buffer_texture(MAX_BULLETS * bullet_struct_size, Texture.T_float, Texture.F_rgba32, Geom.UH_dynamic)

        vformat = GeomVertexFormat.get_v3()
        vdata = GeomVertexData("bullets", vformat, Geom.UH_static)
        vdata.setNumRows(MAX_BULLETS)
        prim = GeomPoints(Geom.UH_static)
        
        # --- THIS IS THE FIX ---
        prim.addConsecutiveVertices(0, MAX_BULLETS)

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode('bullet_geom')
        node.addGeom(geom)
        self.bullet_node = self.render.attachNewNode(node)
        self.bullet_node.setShader(render_shader)
        self.bullet_node.setShaderInput("BulletBuffer", self.bullet_buffer)
        self.bullet_node.set_render_mode_thickness(5)
        self.bullet_node.set_attrib(RenderModeAttrib.make(RenderModeAttrib.M_point))
        
        self.compute_node = NodePath("compute_manager")
        self.compute_node.setShader(compute_shader)
        self.compute_node.setShaderInput("RocketBuffer", self.rocket_buffer)
        self.compute_node.setShaderInput("BulletBuffer", self.bullet_buffer)
        self.compute_node.setShaderInput("world_radius", WORLD_RADIUS)
        self.compute_node.setShaderInput("num_rockets", STARTING_ROCKETS)

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
            points.append(Point3(x, y, z) * WORLD_RADIUS)
        return points

    # In the start_game method

    def start_game(self):
        self.cleanup_game()
        self.clear_ui()
        self.create_world()
        self.setup_gpu_acceleration()
        
        spawn_points = self.generate_spawn_points(STARTING_ROCKETS)
        random.shuffle(spawn_points)

        # --- FIX IS HERE ---
        # Use a bytearray instead of PTA_float for mixed data types.
        buffer_size_bytes = STARTING_ROCKETS * 32
        rocket_data = bytearray(buffer_size_bytes)
        
        for i in range(STARTING_ROCKETS):
            is_player = (i == 0)
            pos = spawn_points[i]
            rocket = Rocket(self, pos, is_player=is_player)
            
            # This attribute is needed to find the rocket's data in the buffer later
            rocket.buffer_index = i
            
            self.all_rockets.append(rocket)
            if is_player: self.player_ref = rocket
            rocket.reparentTo(self.render)
            self.cTrav.addCollider(rocket.c_np, self.coll_handler)

            hitbox_world_pos = self.render.getRelativePoint(rocket, rocket.hitbox_collision_pos)
            # Pack data into the bytearray
            struct.pack_into('3f f i 3f', rocket_data, i * 32, 
                            hitbox_world_pos.x, hitbox_world_pos.y, hitbox_world_pos.z,
                            ROCKET_HITBOX_RADIUS, 1, 0, 0, 0)

        # This will now work correctly with the bytearray
        self.rocket_buffer.set_ram_image(rocket_data)
        self.bullet_write_index = 0

        self.setup_camera()
        self.game_active = True
        self.taskMgr.add(self.game_loop, "GameLoop")

    def cleanup_game(self):
        for r in self.all_rockets: r.destroy()
        self.all_rockets, self.player_ref = [], None
        if hasattr(self, 'world_sphere'): self.world_sphere.removeNode()
        if self.bullet_node: self.bullet_node.removeNode()

    def create_world(self):
        self.world_sphere = create_icosphere(subdivisions=5); self.world_sphere.setScale(WORLD_RADIUS)
        mat = Material(); base_color = LColor(0.1, 0.15, 0.3, 1)
        mat.setAmbient(base_color * 0.6); mat.setDiffuse(base_color * 0.9)
        self.world_sphere.setMaterial(mat, 1); self.world_sphere.reparentTo(self.render)
        self._create_world_grid().reparentTo(self.world_sphere)

    def _create_world_grid(self, num_lat=18, num_lon=36):
        ls = LineSegs("grid"); ls.setThickness(1.0); ls.setColor(0.2, 0.3, 0.6, 0.8)
        radius = 1.005
        for i in range(1, num_lat):
            lat = math.pi * i/num_lat - math.pi/2; r, z = radius * math.cos(lat), radius * math.sin(lat)
            for j in range(num_lon + 1):
                lon = 2 * math.pi * j / num_lon; x, y = r * math.cos(lon), r * math.sin(lon)
                if j == 0: ls.moveTo(x, y, z)
                else: ls.drawTo(x, y, z)
        for i in range(num_lon):
            lon = 2 * math.pi * i / num_lon
            for j in range(num_lat + 1):
                lat = math.pi * j / num_lat - math.pi / 2; r, z = radius * math.cos(lat), radius * math.sin(lon)
                x, y = r * math.cos(lon), r * math.sin(lon)
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
        if not self.player_ref: return
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

    def game_loop(self, task):
        if not self.game_active: return Task.done
        
        self.update_time_dilator()
        dt = globalClock.getDt() * self.time_dilator
        dt = min(dt, 1/30.0) 
        
        rocket_data_view = self.rocket_buffer.modify_ram_image()
        rockets_to_remove = []
        
        for i, rocket in enumerate(self.all_rockets):
            is_active = struct.unpack_from('i', rocket_data_view, rocket.buffer_index * 32 + 16)[0]
            if is_active == 0:
                rockets_to_remove.append(rocket)
                continue

            if rocket.is_player: rocket.control(dt)
            else:
                other_rockets = [r for r in self.all_rockets if r != rocket]
                rocket.update_ai(dt, other_rockets)
            rocket.update(dt)
            
            hitbox_world_pos = self.render.getRelativePoint(rocket, rocket.hitbox_collision_pos)
            struct.pack_into('3f', rocket_data_view, rocket.buffer_index * 32, hitbox_world_pos.x, hitbox_world_pos.y, hitbox_world_pos.z)
        
        if rockets_to_remove:
            active_rockets = []
            for rocket in self.all_rockets:
                if rocket in rockets_to_remove:
                    rocket.destroy()
                else:
                    active_rockets.append(rocket)
            self.all_rockets = active_rockets
            
            # --- FIX IS HERE ---
            # Re-build the rocket buffer from scratch using a bytearray
            new_buffer_size = len(self.all_rockets) * 32
            rocket_data = bytearray(new_buffer_size)

            for i, rocket in enumerate(self.all_rockets):
                rocket.buffer_index = i
                hitbox_world_pos = self.render.getRelativePoint(rocket, rocket.hitbox_collision_pos)
                struct.pack_into('3f f i 3f', rocket_data, i * 32, hitbox_world_pos.x, hitbox_world_pos.y, hitbox_world_pos.z, ROCKET_HITBOX_RADIUS, 1, 0, 0, 0)
            
            # To resize the buffer, you must re-setup the texture before setting the image
            self.rocket_buffer.setup_buffer_texture(new_buffer_size, Texture.T_float, Texture.F_rgba32, Geom.UH_dynamic)
            self.rocket_buffer.set_ram_image(rocket_data)


        self.compute_node.setShaderInput("dt", dt)
        self.compute_node.setShaderInput("num_rockets", len(self.all_rockets))
        attrib = self.compute_node.getAttrib(ShaderAttrib)
        self.win.get_gsg().dispatch_compute((MAX_BULLETS // COMPUTE_GROUP_SIZE, 1, 1), attrib)
        
        self.handle_zoom(dt)
        self.update_camera(dt)
        self.update_game_ui()
        self.cTrav.traverse(self.render)

        if self.game_active:
            if self.player_ref and self.player_ref not in self.all_rockets:
                self.handle_game_over()
            elif self.player_ref and len(self.all_rockets) == 1 and self.all_rockets[0].is_player:
                self.handle_game_won()
        
        return Task.cont

    def spawn_bullet(self, pos, direction, shooter):
        ptr = self.bullet_buffer.modify_ram_image()
        offset = self.bullet_write_index * 32
        struct.pack_into('3f f 3f f', ptr, offset,
                         pos.x, pos.y, pos.z, 0.0,
                         direction.x * BULLET_SPEED, direction.y * BULLET_SPEED, direction.z * BULLET_SPEED,
                         BULLET_LIFETIME)
        self.bullet_write_index = (self.bullet_write_index + 1) % MAX_BULLETS
    
    def on_rocket_collision(self, entry):
        rocket1_np = entry.getFromNodePath().getParent(); rocket2_np = entry.getIntoNodePath().getParent()
        rocket1 = rocket1_np.getPythonTag("owner"); rocket2 = rocket2_np.getPythonTag("owner")
        if not rocket1 or not rocket2: return

        # Mark for removal
        rocket1.is_active = 0
        rocket2.is_active = 0


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
        health_text = f"Hull Integrity: {'100%' if self.player_ref else 'BREACHED'}"
        rockets_left_text = f"Rockets Left: {len(self.all_rockets)}"
        speed_text = f"Game Speed: {self.time_dilator:.2f}x"
        self.update_ui_text("Health", health_text, (-1.3, 0.9), 0.05, align=TextNode.ALeft)
        self.update_ui_text("Enemies", rockets_left_text, (1.3, 0.9), 0.05, align=TextNode.ARight)
        self.update_ui_text("Speed", speed_text, (0, -0.95), 0.05, align=TextNode.ACenter)

    def show_title_screen(self):
        self.clear_ui()
        self.update_ui_text("Title", "ROCKET SPHERE", (0, 0.5), 0.12)
        self.update_ui_text("StartPrompt", "Press R to Start\nA/D to Steer | W/S to Zoom\nSpace to Shoot", (0, 0.2), 0.07)
        self.create_world()
        self.camera.setPos(0, -WORLD_RADIUS * 3, WORLD_RADIUS * 1.5); self.camera.lookAt(0, 0, 0)
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
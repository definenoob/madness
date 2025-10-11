#version 430 core

// Must match COMPUTE_GROUP_SIZE in Python
layout (local_size_x = 128, local_size_y = 1, local_size_z = 1) in;

// Define the data structures for the SSBOs

struct RocketData {
    vec4 position_radius; // xyz = position, w = hitbox radius
    int is_active;
    vec3 padding;
};

struct BulletData {
    vec4 position_padding; // xyz = position
    vec3 velocity;
    float lifetime;
};

// Bind the SSBOs
// layout(std140) ensures standard packing recognizable by the CPU side (struct.pack_into)
layout(std140, binding = 0) buffer RocketBuffer {
    RocketData rockets[];
};

layout(std140, binding = 1) buffer BulletBuffer {
    BulletData bullets[];
};

// Uniform inputs
uniform float dt;
uniform float world_radius;
uniform int num_rockets;
uniform float bullet_radius;

void main() {
    uint index = gl_GlobalInvocationID.x;

    if (index >= bullets.length()) {
        return;
    }

    // Load bullet data
    BulletData bullet = bullets[index];

    if (bullet.lifetime <= 0.0) {
        return;
    }

    // Update lifetime
    bullet.lifetime -= dt;
    
    // Update position
    vec3 new_pos = bullet.position_padding.xyz + bullet.velocity * dt;
    
    // Keep the bullet near the sphere surface
    vec3 new_pos_norm = normalize(new_pos);
    // Offset slightly to prevent clipping
    new_pos = new_pos_norm * (world_radius + 0.1); 

    // Update velocity vector to be tangent to the new position
    bullet.velocity -= new_pos_norm * dot(bullet.velocity, new_pos_norm);

    // Collision Detection (Bullet vs Rockets)
    bool collided = false;
    for (int i = 0; i < num_rockets; ++i) {
        // Ensure we don't check against inactive rockets
        if (rockets[i].is_active == 0) {
            continue;
        }

        vec3 rocket_pos = rockets[i].position_radius.xyz;
        float rocket_radius = rockets[i].position_radius.w;
        
        // Simple sphere-sphere collision check
        float dist_sq = dot(new_pos - rocket_pos, new_pos - rocket_pos);
        float combined_radius = rocket_radius + bullet_radius;
        
        if (dist_sq < (combined_radius * combined_radius)) {
            // Mark rocket as inactive (destroyed)
            // Use atomicExchange to ensure thread safety when writing to the buffer
            atomicExchange(rockets[i].is_active, 0);
            collided = true;
            break; // Bullet is destroyed upon impact
        }
    }

    if (collided) {
        bullet.lifetime = 0.0;
    }

    // Write back updated bullet data
    bullet.position_padding.xyz = new_pos;
    bullets[index] = bullet;
}
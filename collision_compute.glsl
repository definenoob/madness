#version 430

// Define the data structure for a Rocket's hitbox
struct Rocket {
    vec3 position;
    float radius;
    int is_active; // Use as a boolean (1 for active, 0 for destroyed)
    vec3 padding; // GLSL requires structs to be aligned to 16-byte boundaries
};

// Define the data structure for a Bullet
struct Bullet {
    vec3 position;
    float age;
    vec3 velocity;
    float lifetime;
};

// Input/Output buffer for all rockets in the scene
layout(std430, binding = 0) buffer RocketBuffer {
    Rocket rockets[];
};

// Input/Output buffer for all bullets in the scene
layout(std430, binding = 1) buffer BulletBuffer {
    Bullet bullets[];
};

// Global inputs from the Python script
uniform float dt;
uniform float world_radius;
uniform int num_rockets;

// The number of parallel threads to launch (should match the number of bullets)
layout(local_size_x = 128, local_size_y = 1, local_size_z = 1) in;

void main() {
    // Get the unique index for this specific thread/bullet
    uint index = gl_GlobalInvocationID.x;

    // Read this thread's bullet data from the buffer
    Bullet b = bullets[index];

    // If the bullet is already dead, do nothing.
    if (b.lifetime <= 0.0) {
        return;
    }

    // --- 1. Update Physics ---
    b.age += dt;

    // Calculate new position and keep it on the sphere's surface
    vec3 new_pos = b.position + b.velocity * dt;
    vec3 new_pos_norm = normalize(new_pos);
    b.position = new_pos_norm * world_radius;

    // Re-project velocity to be tangent to the new position
    b.velocity -= new_pos_norm * dot(b.velocity, new_pos_norm);

    // --- 2. Collision Detection ---
    bool hit_something = false;
    for (int i = 0; i < num_rockets; i++) {
        // Only check against active rockets
        if (rockets[i].is_active == 1) {
            float dist = distance(b.position, rockets[i].position);
            float min_dist = rockets[i].radius + bullets[index].age * 0.5; // Bullet radius is a placeholder, could be passed in

            if (dist < min_dist) {
                // Collision occurred! Mark the rocket for destruction.
                // atomicExchange ensures that multiple bullets hitting the same rocket
                // in the same frame don't cause a data-writing conflict.
                atomicExchange(rockets[i].is_active, 0);
                hit_something = true;
            }
        }
    }

    // --- 3. Update Bullet State ---
    // If we hit something, or if the bullet's lifetime has expired, mark it for deletion.
    if (hit_something || b.age > b.lifetime) {
        b.lifetime = -1.0; // Set lifetime to a negative value to signify it's dead
    }

    // Write the updated bullet data back to the buffer
    bullets[index] = b;
}
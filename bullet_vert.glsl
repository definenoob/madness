#version 330

// Use the same Bullet data structure
struct Bullet {
    vec3 position;
    float age;
    vec3 velocity;
    float lifetime;
};

// Input buffer of all bullets (read-only for this shader)
layout(std430, binding = 1) buffer BulletBuffer {
    Bullet bullets[];
};

// Standard Panda3D transform matrix
uniform mat4 p3d_ModelViewProjectionMatrix;

void main() {
    // Get this bullet's data
    Bullet b = bullets[gl_VertexID];

    // If the bullet is alive, calculate its screen position.
    // If it's dead (lifetime < 0), set its size to 0 to hide it.
    if (b.lifetime > 0.0) {
        gl_Position = p3d_ModelViewProjectionMatrix * vec4(b.position, 1.0);
        gl_PointSize = 10.0; // Make points 10 pixels wide
    } else {
        gl_Position = vec4(0, 0, 0, 0); // Effectively hides the vertex
        gl_PointSize = 0.0;
    }
}
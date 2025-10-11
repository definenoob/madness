#version 430 core

// Standard Panda3D input
uniform mat4 p3d_ModelViewProjectionMatrix;

struct BulletData {
    vec4 position_padding;
    vec3 velocity;
    float lifetime;
};

// Bind the SSBO (must match the binding point in the compute shader)
layout(std140, binding = 1) buffer BulletBuffer {
    BulletData bullets[];
};

// Output to fragment shader
out vec4 fragColor;

void main() {
    // Use the vertex ID to look up the corresponding bullet data
    int index = gl_VertexID;
    BulletData bullet = bullets[index];

    if (bullet.lifetime > 0.0) {
        // Set the position from the buffer data
        gl_Position = p3d_ModelViewProjectionMatrix * vec4(bullet.position_padding.xyz, 1.0);
        
        // Simple visualization color (e.g., yellow/orange)
        fragColor = vec4(1.0, 0.8, 0.5, 1.0);
    } else {
        // If the bullet is inactive, discard it (by setting position to 0)
        gl_Position = vec4(0.0, 0.0, 0.0, 0.0);
        fragColor = vec4(0.0);
    }
}
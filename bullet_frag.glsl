#version 330

// The final output color
out vec4 fragColor;

void main() {
    // Make the point a circle instead of a square
    if (length(gl_PointCoord - vec2(0.5)) > 0.5) {
        discard;
    }
    fragColor = vec4(1.0, 0.8, 0.5, 1.0); // Bullet Color
}
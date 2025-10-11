#version 430 core

// Input from vertex shader
in vec4 fragColor;

// Output color
out vec4 outputColor;

void main() {
    outputColor = fragColor;
}
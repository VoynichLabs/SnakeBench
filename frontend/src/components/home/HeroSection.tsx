"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useRef } from "react";
import { useTopMatch } from "@/hooks/useTopMatch";

export default function HeroSection() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { href: topMatchHref } = useTopMatch();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas dimensions to match parent container
    const resizeCanvas = () => {
      const container = canvas.parentElement;
      if (container) {
        canvas.width = container.offsetWidth;
        canvas.height = container.offsetHeight;
      }
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Snake class
    class Snake {
      x: number;
      y: number;
      size: number;
      color: string;
      direction: number;
      speed: number; // Now represents frame delay for movement
      tail: { x: number; y: number }[];
      maxLength: number;
      moveCounter: number; // Counter for implementing frame delay

      constructor(initialCanvasWidth: number, initialCanvasHeight: number) {
        this.size = 12;
        // Initialize position on the grid
        this.x =
          Math.floor(
            Math.random() * Math.floor(initialCanvasWidth / this.size)
          ) * this.size;
        this.y =
          Math.floor(
            Math.random() * Math.floor(initialCanvasHeight / this.size)
          ) * this.size;

        this.color = ["#4ade80", "#60a5fa", "#f97316", "#8b5cf6", "#000000"][
          Math.floor(Math.random() * 5)
        ];
        this.direction = Math.floor(Math.random() * 4); // 0: right, 1: down, 2: left, 3: up
        // Speed is now frames to wait before moving one grid unit.
        // Lower number means faster perceived speed. e.g., 1-3 frames wait.
        this.speed = Math.floor(Math.random() * 10) + 3;
        this.moveCounter = 0;
        this.tail = [{ x: this.x, y: this.y }]; // Tail starts at the quantized position
        this.maxLength = 30 + Math.floor(Math.random() * 15);
      }

      update(canvasWidth: number, canvasHeight: number) {
        this.moveCounter++;
        if (this.moveCounter < this.speed) {
          return; // Wait for enough frames before moving
        }
        this.moveCounter = 0; // Reset counter

        // Change direction randomly
        if (Math.random() < 0.02) {
          this.direction = Math.floor(Math.random() * 4);
        }

        // Move based on direction by one grid unit (this.size)
        switch (this.direction) {
          case 0:
            this.x += this.size;
            break; // right
          case 1:
            this.y += this.size;
            break; // down
          case 2:
            this.x -= this.size;
            break; // left
          case 3:
            this.y -= this.size;
            break; // up
        }

        // Wrap around edges, aligning to the grid
        const numCols = Math.floor(canvasWidth / this.size);
        const numRows = Math.floor(canvasHeight / this.size);

        if (this.x < 0) {
          this.x = (numCols - 1) * this.size;
        } else if (this.x >= numCols * this.size) {
          this.x = 0;
        }

        if (this.y < 0) {
          this.y = (numRows - 1) * this.size;
        } else if (this.y >= numRows * this.size) {
          this.y = 0;
        }
        
        // Ensure x and y are always on the grid, especially if canvas resizes
        // and numCols/Rows leads to an off-grid calculation temporarily.
        // This might be overly cautious if canvas resize is handled perfectly for grid alignment.
        this.x = Math.round(this.x / this.size) * this.size;
        this.y = Math.round(this.y / this.size) * this.size;


        // Add current position to tail
        this.tail.push({ x: this.x, y: this.y });

        // Limit tail length
        if (this.tail.length > this.maxLength) {
          this.tail.shift();
        }
      }

      draw(ctx: CanvasRenderingContext2D) {
        // Draw tail segments
        for (let i = 0; i < this.tail.length; i++) {
          const segment = this.tail[i];
          const alpha = i / this.tail.length; // Fade out the tail
          ctx.fillStyle =
            this.color +
            Math.floor(alpha * 255)
              .toString(16)
              .padStart(2, "0");
          ctx.fillRect(segment.x, segment.y, this.size, this.size);
        }
      }
    }

    // Create snakes
    const snakes: Snake[] = [];
    const SNAKE_COUNT = 20; // Adjust this number up or down for more or fewer snakes
    
    for (let i = 0; i < SNAKE_COUNT; i++) {
      snakes.push(
        new Snake(canvas.width, canvas.height) // Pass canvas dimensions for grid initialization
      );
    }

    // Animation loop
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      snakes.forEach((snake) => {
        snake.update(canvas.width, canvas.height);
        snake.draw(ctx);
      });

      requestAnimationFrame(animate);
    };

    animate();

    // Cleanup
    return () => {
      window.removeEventListener("resize", resizeCanvas);
    };
  }, []);

  return (
    <div className="bg-white border-b border-gray-200 relative overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-30"
      />
      <div className="max-w-7xl mx-auto py-16 px-4 sm:py-24 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center">
          <h1 className="text-4xl font-press-start text-gray-900 sm:text-5xl sm:tracking-tight lg:text-6xl">
            LLMs Battle Snake
          </h1>
          <p className="mt-4 max-w-2xl mx-auto text-xl text-gray-500 font-mono">
            Watch AI models compete in real-time snake battles. Strategic
            thinking, path-finding, and decision-making on display.
          </p>
          <div className="mt-8 flex justify-center font-mono">
            <Button asChild className="font-mono">
              <Link href={topMatchHref}>
                Watch Top Match
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

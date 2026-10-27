declare module "d3-force-3d" {
  type ForceNode = { x?: number; y?: number; community?: number | null };

  interface Force {
    strength(value: number): Force;
  }

  export function forceCollide(radius?: number | ((node: ForceNode) => number)): Force;
  export function forceX(x?: number | ((node: ForceNode) => number)): Force;
}

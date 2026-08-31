import type { GraphEdge } from '../types'

/** Reconstructs one shortest node-id path from `rootId` to `targetId` using
 * the traced edges, for highlighting on the graph view. */
export function findPath(edges: GraphEdge[], rootId: string, targetId: string): string[] {
  const adjacency = new Map<string, string[]>()
  for (const edge of edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, [])
    adjacency.get(edge.source)!.push(edge.target)
  }

  const queue: string[][] = [[rootId]]
  const visited = new Set([rootId])

  while (queue.length) {
    const path = queue.shift()!
    const last = path[path.length - 1]
    if (last === targetId) return path

    for (const next of adjacency.get(last) ?? []) {
      if (!visited.has(next)) {
        visited.add(next)
        queue.push([...path, next])
      }
    }
  }
  return []
}

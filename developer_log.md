# Developer Log - Interactive 3D Chatbot

> [!IMPORTANT]
> **Quy tắc quản lý Log:**
> 1. Mỗi khi bắt đầu một task mới, Agent **phải xóa các log của task cũ** để tiết kiệm dung lượng và giữ file súc tích.
> 2. Luôn cập nhật trạng thái task hiện tại.
> 3. Liên kết đến [BRAIN.md](BRAIN.md), [Gemini.md](gemini.md), và [Claude.md](claude.md).

---

## Task: Stage 3 (Tier 3) — Facecap Sample Avatar
**Agent:** Claude (Senior AI Engineer)
**Status:** Completed
**Date:** 2026-05-04

### Các thay đổi thực hiện:

**Model:** `frontend/public/models/avatar.glb`
- Nguồn: Three.js facecap sample (332KB, GLB v2)
- **52 ARKit blendshapes** đầy đủ trên head mesh
- Nodes: `head` (morph mesh), `teeth`, `eyeLeft`, `eyeRight`

**Files thay đổi:**
- `frontend/src/components/Avatar.tsx` — traverse scene tìm morph mesh, expose `avatarMorphRef` (module-level), idle blink, emotion blendshapes via lerp
- `frontend/src/components/Scene.tsx` — camera gần hơn (`fov: 38, z: 1.4`) phù hợp head-only model
- `frontend/src/types/visemeMapping.ts` [NEW] — bảng mapping Rhubarb phoneme (A-X) → ARKit blendshape weights

**`avatarMorphRef` (cho Stage 4):**
```ts
export const avatarMorphRef = {
  mesh: SkinnedMesh | null,
  dict: Record<string, number>,   // morphTargetDictionary
  influences: number[],           // morphTargetInfluences (live reference)
}
export function setMorph(name: string, value: number): void
export function resetMorphs(names: string[]): void
```

**Rhubarb → ARKit mapping** (`visemeMapping.ts`):
```
A (ah)  → jawOpen:0.8, mouthFunnel:0.2, mouthLowerDown:0.4
B (pbm) → mouthClose:0.9, mouthPress:0.4
C (th)  → jawOpen:0.35, mouthLowerDown:0.6, mouthUpperUp:0.4
D (ee)  → jawOpen:0.2, mouthSmile:0.5, mouthStretch:0.3
E (eh)  → jawOpen:0.45, mouthStretch:0.4
F (fv)  → mouthRollLower:0.6, jawOpen:0.1
G (oh)  → jawOpen:0.55, mouthFunnel:0.6
H (oo)  → mouthPucker:0.7, mouthFunnel:0.5, jawOpen:0.2
X       → (silence, all 0)
```

### Ghi chú cho Agent tiếp theo (Stage 4):
- Đừng quên xóa phần log này khi bắt đầu Stage 4!
- Stage 4 cần: import `{ avatarMorphRef, setMorph, resetMorphs, VISEME_MAP, ALL_VISEME_KEYS }` từ Avatar và visemeMapping
- Rhubarb output JSON: `[{ "start": 0.0, "end": 0.1, "value": "A" }, ...]`
- Chạy Rhubarb trên backend (Windows binary hoặc Docker), expose kết quả trong `AudioChunkPayload.visemes`

---

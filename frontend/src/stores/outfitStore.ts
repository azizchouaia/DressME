import { create } from 'zustand'
import type { Outfit, OutfitSlot } from '../types'
import { EMPTY_SELECTION, selectionFromOutfit, type SlotSelection } from '../utils/garments'

interface OutfitEditorState {
  selection: SlotSelection
  /** The saved outfit being edited, if any. */
  outfit: Outfit | null
  dirty: boolean
  setSlot: (slot: OutfitSlot, itemId: string | null) => void
  loadOutfit: (outfit: Outfit) => void
  markSaved: (outfit: Outfit) => void
  startNew: (selection?: SlotSelection) => void
}

export const useOutfitEditor = create<OutfitEditorState>()((set) => ({
  selection: EMPTY_SELECTION,
  outfit: null,
  dirty: false,
  setSlot: (slot, itemId) =>
    set((state) => ({ selection: { ...state.selection, [slot]: itemId }, dirty: true })),
  loadOutfit: (outfit) => set({ outfit, selection: selectionFromOutfit(outfit), dirty: false }),
  markSaved: (outfit) => set({ outfit, selection: selectionFromOutfit(outfit), dirty: false }),
  startNew: (selection = EMPTY_SELECTION) => set({ outfit: null, selection, dirty: false }),
}))

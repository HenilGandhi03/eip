import { create } from 'zustand'

export const useStore = create((set) => ({
  // View
  activeView: 'timeline',
  setActiveView: (v) => set({ activeView: v }),

  // Selected items
  selectedEventId: null,
  setSelectedEventId: (id) => set({ selectedEventId: id }),
  selectedEntityId: null,
  setSelectedEntityId: (id) => set({ selectedEntityId: id }),

  // Filters
  filters: {
    categories: [],
    countries:  ['IND'],
    startDate:  null,
    endDate:    null,
    query:      '',
  },
  setFilter: (key, value) =>
    set((s) => ({ filters: { ...s.filters, [key]: value } })),
  toggleCategory: (cat) =>
    set((s) => {
      const cats = s.filters.categories
      return {
        filters: {
          ...s.filters,
          categories: cats.includes(cat)
            ? cats.filter((c) => c !== cat)
            : [...cats, cat],
        },
      }
    }),
  resetFilters: () =>
    set({ filters: { categories: [], countries: ['IND'], startDate: null, endDate: null, query: '' } }),
}))

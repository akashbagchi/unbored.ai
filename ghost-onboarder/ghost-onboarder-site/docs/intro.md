---
sidebar_position: 1
---

# akashbagchi/modern-portfolio - Architecture Overview

# Modern Portfolio Codebase Documentation

## Understanding the Codebase

This project follows a Nuxt 3-based architecture with a clear separation between server and client concerns. The codebase is structured as a monolithic application with distinct frontend and backend layers, using Nuxt's built-in server capabilities alongside a PostgreSQL database.

The most important concepts to grasp are:

1. **Component-Driven Architecture**: The UI is built entirely from Vue components, with shared logic extracted into composables. This pattern drives both the organization and the development workflow.

2. **Server-Side Integration**: Unlike typical Nuxt apps that might rely on external APIs, this project includes its own backend implementation using Nuxt's server handlers and Drizzle ORM for database operations.

## Code Organization & Flow

**`components/`**
- **Purpose**: Houses all Vue components, split between `layout/` for structural components and `ui/` for reusable interface elements
- **Key files**: `NavBar.vue` manages navigation and theme switching, while `HeroSection.vue` and `ProjectCard.vue` handle core content display
- **When you'll touch this**: Adding new UI features or modifying existing ones
- **Gotchas**: Components rely heavily on composables for shared logic - always check `composables/` when modifying components

**`composables/`**
- **Purpose**: Centralizes reusable logic and state management
- **Key files**: `use-theme.ts` manages dark/light mode, `use-mobile.ts` handles responsive behavior
- **When you'll touch this**: Adding new shared functionality or modifying existing behavior that spans multiple components
- **Gotchas**: Changes here can affect multiple components - carefully check usage with your IDE's "Find References" feature

**`server/`**
- **Purpose**: Contains all backend logic including API endpoints and database operations
- **Key files**: `db/schema.ts` defines database structure, `api/projects/*.ts` handle CRUD operations
- **When you'll touch this**: Modifying data models or API endpoints
- **Gotchas**: Changes to schema require running migrations (`pnpm db:migrate`), and API changes may need updates to corresponding frontend calls

**`pages/`**
- **Purpose**: Defines the application's routing structure and page-level components
- **Key files**: `index.vue` is the landing page, `projects/index.vue` manages project listing
- **When you'll touch this**: Adding new routes or modifying page-level layouts
- **Gotchas**: Pages automatically become routes in Nuxt - be mindful of file naming and placement

## Data Flow Paths

**Project Listing Flow:**
1. User visits `/projects`
2. `pages/projects/index.vue` triggers `useProjects()` composable
3. Composable calls `/api/projects` endpoint
4. Server handler in `server/api/projects.get.ts` queries database via Drizzle
5. Data flows back through the chain and renders via `ProjectCard.vue` components

**Theme Switching Flow:**
1. User clicks theme toggle in `NavBar.vue`
2. `useTheme()` composable updates state
3. Changes propagate through `layouts/default.vue`
4. Theme preference is persisted to localStorage
5. Tailwind classes update throughout the app

## Key Architectural Decisions

**Component Organization**
The split between `layout/` and `ui/` components creates a clear separation of concerns. Layout components handle structural elements and app-wide features, while UI components are more focused and reusable. This organization makes it easier to maintain consistency and reduce duplication.

**Database Integration**
The project uses Drizzle ORM with PostgreSQL, hosted on Neon's serverless platform. This choice enables:
- Type-safe database operations
- Easy schema migrations
- Serverless deployment compatibility
- Cost-effective scaling

**State Management**
Rather than using Pinia or Vuex, the project leverages Vue's Composition API through composables. This approach:
- Reduces boilerplate compared to traditional state management
- Keeps state close to where it's used
- Makes testing and maintenance easier
- Allows for granular code-splitting

**Mobile-First Approach**
The codebase heavily emphasizes mobile support through:
- Dedicated mobile detection via `use-mobile.ts`
- Conditional rendering in components
- Mobile-specific UI elements like `MobileAlert.vue`
- Responsive Tailwind classes throughout

## Module Dependencies

The codebase has several key dependency hubs:

- `composables/use-mobile.ts` is imported by many components for responsive behavior
- `server/db/config.ts` and `schema.ts` are central to all API endpoints
- `types/project.ts` defines interfaces used throughout the project

Leaf nodes (only import, never imported):
- Page components (`pages/*.vue`)
- API endpoint handlers
- Individual UI components

There are no circular dependencies, but be aware that changes to core types in `types/` or database schema can have wide-ranging effects.

## Common Pain Points

Based on issue history, new developers should be aware of:

1. **Accessibility Concerns**: The navbar and navigation links need careful attention to ARIA attributes and roles. When modifying navigation components, ensure you maintain accessibility standards.

2. **Mobile Responsiveness**: The mobile-first approach requires testing on various screen sizes. Use the `useMobile()` composable consistently rather than creating new mobile detection logic.

3. **Database Schema Changes**: Modifications to `server/db/schema.ts` require migration handling. Always run `pnpm db:generate` and `pnpm db:migrate` after schema changes.

---

*This documentation was automatically generated by Ghost Onboarder using Claude AI.*

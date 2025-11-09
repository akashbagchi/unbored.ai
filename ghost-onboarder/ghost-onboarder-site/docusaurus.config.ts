import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'akashbagchi/modern-portfolio Documentation',
  tagline: 'Auto-generated documentation for akashbagchi/modern-portfolio',
  favicon: 'img/favicon.ico',

  // ↓ Basic site URL setup for local/demo hosting
  url: 'http://localhost:3000',
  baseUrl: '/',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: undefined, // hides "Edit this page"
        },
        blog: {
          showReadingTime: false,
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {
      respectPrefersColorScheme: true,
    },

    navbar: {
      title: 'akashbagchi/modern-portfolio Documentation',
      logo: {
        alt: 'Ghost Onboarder Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Architecture Overview',
        },
        { to: '/graph', label: 'Graph View', position: 'right' }, // 👈 keep this
      ],
    },

    footer: {
      style: 'dark',
      links: [
        {
          title: 'Resources',
          items: [
            { label: 'Architecture Overview', to: '/docs/intro' },
            { label: 'Graph View', to: '/graph' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Ghost Onboarder. Built with Docusaurus.`,
    },

    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;

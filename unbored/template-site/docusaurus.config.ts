import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
    title: 'unbored - Claude Builder HackASU',
    tagline: 'Take the boredom out of onboarding',
    favicon: 'img/hackasu.png',

    // ↓ Basic site URL setup for local/demo hosting
    url: 'http://localhost:3000',
    baseUrl: '/',

    onBrokenLinks: 'throw',
    onBrokenMarkdownLinks: 'warn',

    i18n: {
        defaultLocale: 'en',
        locales: ['en'],
    },

    clientModules: ['./src/resizeObserverFix.ts'],

    presets: [
        [
            'classic',
            {
                docs: {
                    sidebarPath: './sidebars.ts',
                    editUrl: undefined, // hides "Edit this page"
                    routeBasePath: '/', // docs become the site root
                },
                blog: false, // disable unused blog plugin
                theme: {
                    customCss: './src/css/custom.css',
                },
            } satisfies Preset.Options,
        ],
    ],

    themeConfig: {
        image: 'img/unbored-social-card.png',
        colorMode: {
            defaultMode: 'light',
            disableSwitch: false,
        },

        navbar: {
            title: 'Onboarding Knowledge Base',
            logo: {
                alt: 'unbored.AI Logo',
                src: 'img/logo.svg',
            },
            items: [
                { to: '/graph', label: 'Graph View', position: 'right' },
            ],
        },

        footer: {
            style: 'light',
            links: [
                {
                    title: 'Resources',
                    items: [
                        { label: 'Graph View', to: '/graph' },
                    ],
                },
            ],
            copyright: `Copyright © ${new Date().getFullYear()} unbored.AI. Built with Docusaurus.`,
        },

        prism: {
            theme: prismThemes.github,
            darkTheme: prismThemes.vsDark,
        },
    } satisfies Preset.ThemeConfig,
};

export default config;

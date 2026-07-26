/**
 * Display directory.
 *
 * Console screens are numbered, and both the navigation rail and the global
 * header read the same registry so a screen's code and name can never disagree
 * between them.
 */

export interface DisplayEntry {
  path: string;
  code: string;
  name: string;
  /** Short description shown in the navigation rail. */
  hint: string;
}

export const DISPLAYS: DisplayEntry[] = [
  {
    path: '/',
    code: 'DISP-01',
    name: 'Live Monitor',
    hint: 'Transition risk & actions',
  },
  {
    path: '/correlations',
    code: 'DISP-02',
    name: 'Correlations',
    hint: 'Discovered relationships',
  },
  {
    path: '/events',
    code: 'DISP-03',
    name: 'Event History',
    hint: 'All recorded transitions',
  },
  {
    path: '/feedback',
    code: 'DISP-04',
    name: 'Feedback Log',
    hint: 'Acknowledge / reject history',
  },
  {
    path: '/settings',
    code: 'DISP-05',
    name: 'Settings',
    hint: 'Cache & stored data resets',
  },
];

export const displayFor = (pathname: string): DisplayEntry =>
  DISPLAYS.find((entry) => entry.path === pathname) ?? DISPLAYS[0];

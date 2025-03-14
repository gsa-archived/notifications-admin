const baseUrl = 'http://localhost:6012';

// List of routes with paths and labels
const sublinks = [
  { label: 'Homepage', path: '/' },
  { label: 'Add Service', path: '/add-service' },
  { label: 'Get Started', path: '/using-notify/get-started' },
  { label: 'Trial Mode', path: '/using-notify/trial-mode' },
  { label: 'Pricing', path: '/using-notify/pricing' },
  { label: 'Delivery Status', path: '/using-notify/delivery-status' },
  { label: 'How To', path: '/using-notify/how-to' },
  { label: 'Support', path: '/support' },
  { label: 'Best Practices', path: '/using-notify/best-practices' },
  { label: 'Clear Goals', path: '/using-notify/best-practices/clear-goals' },
  {
    label: 'Rules And Regulations',
    path: '/using-notify/best-practices//rules-and-regulations',
  },
  { label: 'Establish Trust', path: '/using-notify/best-practices//establish-trust' },
  {
    label: 'Write For Action',
    path: '/using-notify/best-practices//write-for-action',
  },
  {
    label: 'Multiple Languages',
    path: '/using-notify/best-practices//multiple-languages',
  },
  {
    label: 'Benchmark Performance',
    path: '/using-notify/best-practices//benchmark-performance',
  },
  {
    label: 'About',
    path: '/about',
  },
  {
    label: 'Why Text Messaging',
    path: '/about/why-text-messaging',
  },
  {
    label: 'Security',
    path: '/about/security',
  },
  {
    label: 'Notify.gov Service Ending',
    path: '/notify-service-ending',
  },

  // Add more links here as needed
];

const createFullUrl = (base, path) => `${base}${path}`;

// Build url using base and path
const constructUrls = (base, sublinks) =>
  sublinks.reduce((acc, { label, path }) => {
    return { ...acc, [label]: createFullUrl(base, path) };
  }, {});

module.exports = {
  baseUrl,
  urls: constructUrls(baseUrl, sublinks),
};

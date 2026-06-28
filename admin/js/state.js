export const state = {
  currentTab: 'summary',
  isFetching: false,
  isTotalListOpen: true,
  rawDevices: [],
  rawLteData: [],
  rawDestinations: [],
  openedGroups: {},
  destinationsGridApi: null,
  logsGridApi: null,
  devicesGridApi: null,
  deviceViewMode: 'accordion',
  pastDateStrs: [],
  activeDate: 'today',
  selectedDestinationDate: null,
  selectedSiteFilter: 'all',
  lastApiData: null
};

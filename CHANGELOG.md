# Changelog

## 0.1.0 (2026-11-17)


### Features

* **calendar:** list the agenda's and day view's parts for screen tests ([ad1ba86](https://github.com/igrybkov/daruma/commit/ad1ba8647301b7e777ec755b877a57a9e58fe0ad))
* **demos:** caption blocks and touch marks ([a6e212d](https://github.com/igrybkov/daruma/commit/a6e212dcbaa91a6f8e97f3e5b5a4dabdb0a0e515))
* **desktop:** take the API port from DARUMA_API_PORT ([f508b24](https://github.com/igrybkov/daruma/commit/f508b2417f10b9347d9a313a70de21d4996926a4))


### Bug Fixes

* **core:** one loop drives the idle glances and blinks ([23ec7e0](https://github.com/igrybkov/daruma/commit/23ec7e0c84845b803769023073ac7c0bcc479f6a))
* **demos:** every device listens on a free API port ([7fa8e14](https://github.com/igrybkov/daruma/commit/7fa8e141b4fabbbf7d5c5ec93350e6c9fbad5df0))
* **demos:** fake /dev/urandom through fopen64 on Linux too ([fceb530](https://github.com/igrybkov/daruma/commit/fceb53032d5eb40b45ada4bbf47d4e8f4adda9e8))
* **demos:** give each parallel run a free API port ([3f6755c](https://github.com/igrybkov/daruma/commit/3f6755cbbb3475db93efa6758b58f13dd2006d50))
* **demos:** step the clock only after a whole turn at the new time ([d756be8](https://github.com/igrybkov/daruma/commit/d756be899cbe386b8b60f340efe346187435badd))
* **examples:** the desktop main menu matches the framework default ([1a8073c](https://github.com/igrybkov/daruma/commit/1a8073c4c57cbef699575e7610da0885ea315596))
* **tests:** no line continuation in a test_frames.cpp comment ([e7beb22](https://github.com/igrybkov/daruma/commit/e7beb22ccb4cbbed186b132484956f1b414eba6b))


### Performance Improvements

* **demos:** keep each build's objects when builds take turns ([e7a7646](https://github.com/igrybkov/daruma/commit/e7a7646f65a1c8df5234eaacfd08b661c44a8920))
* **demos:** keep the drawn persona art between builds ([af531da](https://github.com/igrybkov/daruma/commit/af531daad5a0dcf813cfe30d3e4a001b1c53d0ee))
* **demos:** run personas and scenarios in parallel ([7f26da1](https://github.com/igrybkov/daruma/commit/7f26da12837f72b39f27357bf66a3713f4e167d0))
* **demos:** run the pytest screen tests in parallel ([ddb9b93](https://github.com/igrybkov/daruma/commit/ddb9b9330cf889b8d32870f929acb2c751ccb688))
* faster CI and test runs: cached art and builds, uv lock, pytest-xdist ([c0c6acd](https://github.com/igrybkov/daruma/commit/c0c6acd3b3c6793d495db0f508e65882448fe4d0))


### Reverts

* fix(demos): fake /dev/urandom through fopen64 on Linux too ([ca83d96](https://github.com/igrybkov/daruma/commit/ca83d96fa1273a45d16e0f3d72a7ad8bab6f7cfa))


### Documentation

* add READMEs for the examples and the packages ([0111db9](https://github.com/igrybkov/daruma/commit/0111db9361496a5ad0f4f1b15ff86524c3214660))
* **architecture:** add a writing guide and scope topics by task ([97ee6e2](https://github.com/igrybkov/daruma/commit/97ee6e2b36d021c214de168056ff3d32860c16c7))
* **architecture:** let readers follow links past the first topic ([f608a93](https://github.com/igrybkov/daruma/commit/f608a93c531e7b8dc499f4e09f713d594fb28739))
* **architecture:** split ARCHITECTURE.md into topics by kind of work ([3fb3903](https://github.com/igrybkov/daruma/commit/3fb3903accdd17077bc905bbe779a6ff7af3d606))
* **architecture:** split ARCHITECTURE.md into topics by kind of work ([768c0ac](https://github.com/igrybkov/daruma/commit/768c0ac6412ef65ea50ef5fb494f2d8dc217c353))
* **blueprints:** move the blueprint list next to the blueprints ([99f505e](https://github.com/igrybkov/daruma/commit/99f505e9e7f53237b96b784f0d152dee9c980433))
* **packages:** say what a package is and why the device uses them ([14cdbb4](https://github.com/igrybkov/daruma/commit/14cdbb4bb4d0111507d421ab46689467cfe6c21b))
* re-record the demos with the real menu and touch marks ([ba8bf38](https://github.com/igrybkov/daruma/commit/ba8bf38c1c680c3f5322d958c634395c42101faf))
* run the screen tests in parallel ([295f48c](https://github.com/igrybkov/daruma/commit/295f48c013a22796c37d5fd6bcb272a4e91a8c9c))
* show the device at work at the top of the README ([7276102](https://github.com/igrybkov/daruma/commit/727610229e2c91db0471951482726966e1fbfa9e))
* show the device at work at the top of the README ([50c1ea2](https://github.com/igrybkov/daruma/commit/50c1ea222a8e8065535f4db02eab754eb02cc4bd))
* the screen tests run on macOS and Linux ([cd31025](https://github.com/igrybkov/daruma/commit/cd31025a2527558b6217a3b7a2ae3f67ad1d80a0))
* use the make goals in the contributor docs ([c3fdbce](https://github.com/igrybkov/daruma/commit/c3fdbce67f753404812647032ee74c9df5210782))
* write the folder READMEs for a reader new to Daruma ([2916f0b](https://github.com/igrybkov/daruma/commit/2916f0b30696bbdc5381329bccfcc33c7626e203))

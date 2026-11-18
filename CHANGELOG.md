# Changelog

## 0.1.0 (2026-11-18)


### Features

* **calendar:** list the agenda's and day view's parts for screen tests ([ad1ba86](https://github.com/igrybkov/daruma/commit/ad1ba8647301b7e777ec755b877a57a9e58fe0ad))
* **demos:** caption blocks and touch marks ([a6e212d](https://github.com/igrybkov/daruma/commit/a6e212dcbaa91a6f8e97f3e5b5a4dabdb0a0e515))
* **demos:** find persona folders through DARUMA_PERSONA_PATH ([27e2891](https://github.com/igrybkov/daruma/commit/27e28916beec5b51f24c8533325882331405e484))
* **demos:** find persona folders through DARUMA_PERSONA_PATH ([f4d434b](https://github.com/igrybkov/daruma/commit/f4d434b035fe96ead9b8ecf98f78683a6f2811a3))
* **desktop:** take the API port from DARUMA_API_PORT ([f508b24](https://github.com/igrybkov/daruma/commit/f508b2417f10b9347d9a313a70de21d4996926a4))


### Bug Fixes

* **core:** one loop drives the idle glances and blinks ([23ec7e0](https://github.com/igrybkov/daruma/commit/23ec7e0c84845b803769023073ac7c0bcc479f6a))
* **demos:** every device listens on a free API port ([7fa8e14](https://github.com/igrybkov/daruma/commit/7fa8e141b4fabbbf7d5c5ec93350e6c9fbad5df0))
* **demos:** fake /dev/urandom through fopen64 on Linux too ([fceb530](https://github.com/igrybkov/daruma/commit/fceb53032d5eb40b45ada4bbf47d4e8f4adda9e8))
* **demos:** give each parallel run a free API port ([3f6755c](https://github.com/igrybkov/daruma/commit/3f6755cbbb3475db93efa6758b58f13dd2006d50))
* **demos:** step the clock only after a whole turn at the new time ([d756be8](https://github.com/igrybkov/daruma/commit/d756be899cbe386b8b60f340efe346187435badd))
* **demos:** stop the program when a device fails to start ([e3bd808](https://github.com/igrybkov/daruma/commit/e3bd8084bf4a57c0984e8d6c195be7999712db70))
* **examples:** the desktop main menu matches the framework default ([1a8073c](https://github.com/igrybkov/daruma/commit/1a8073c4c57cbef699575e7610da0885ea315596))
* **tests:** no line continuation in a test_frames.cpp comment ([e7beb22](https://github.com/igrybkov/daruma/commit/e7beb22ccb4cbbed186b132484956f1b414eba6b))


### Performance Improvements

* **demos:** keep each build's objects when builds take turns ([e7a7646](https://github.com/igrybkov/daruma/commit/e7a7646f65a1c8df5234eaacfd08b661c44a8920))
* **demos:** keep the drawn persona art between builds ([af531da](https://github.com/igrybkov/daruma/commit/af531daad5a0dcf813cfe30d3e4a001b1c53d0ee))
* **demos:** run personas and scenarios in parallel ([7f26da1](https://github.com/igrybkov/daruma/commit/7f26da12837f72b39f27357bf66a3713f4e167d0))
* **demos:** run the pytest screen tests in parallel ([ddb9b93](https://github.com/igrybkov/daruma/commit/ddb9b9330cf889b8d32870f929acb2c751ccb688))
* **demos:** take the desktop time zone from HA, one build for every zone ([2ca1046](https://github.com/igrybkov/daruma/commit/2ca1046d2af5af3f3ac1e0728179733a27332353))
* **demos:** take the desktop time zone from HA, one build for every zone ([7d05f52](https://github.com/igrybkov/daruma/commit/7d05f52443d91bfa2938c5f3e3230e86ed3bf29c))
* **desktop:** draw into a RAM canvas and upload once per frame ([4fede81](https://github.com/igrybkov/daruma/commit/4fede8194c5e71bb21a9258a4ac5333cfd6d9769))
* **desktop:** draw into a RAM canvas and upload once per frame ([83113bc](https://github.com/igrybkov/daruma/commit/83113bc06a75bb39bcdd38ca25a2fbf715f8202e))
* faster CI and test runs: cached art and builds, uv lock, pytest-xdist ([c0c6acd](https://github.com/igrybkov/daruma/commit/c0c6acd3b3c6793d495db0f508e65882448fe4d0))
* **pixel:** draw each persona about 10x faster, same pixels ([0b47281](https://github.com/igrybkov/daruma/commit/0b4728144fb9d4f841319a563ec632f8518b67f6))
* **pixel:** draw each persona about 10x faster, same pixels ([dabbd48](https://github.com/igrybkov/daruma/commit/dabbd485c31f5d868c8456f79050c0f87ee1bfb9))
* **sprites:** encode frame sets about 2.4x faster, same bytes ([7489efd](https://github.com/igrybkov/daruma/commit/7489efdfaf95c84aa275db8b7838f2fab4974171))
* **tests:** host tests in about a third of the time ([60ba331](https://github.com/igrybkov/daruma/commit/60ba331821270a37574bd92bacd3308179f1754c))
* **tests:** steal work across workers and cut the slow host tests ([809874d](https://github.com/igrybkov/daruma/commit/809874d6bcd70a76bbfefcc2229eddf43c0cff0e))


### Reverts

* fix(demos): fake /dev/urandom through fopen64 on Linux too ([ca83d96](https://github.com/igrybkov/daruma/commit/ca83d96fa1273a45d16e0f3d72a7ad8bab6f7cfa))


### Documentation

* add READMEs for the examples and the packages ([0111db9](https://github.com/igrybkov/daruma/commit/0111db9361496a5ad0f4f1b15ff86524c3214660))
* **agents:** open a draft pull request while the work is in progress ([78419dd](https://github.com/igrybkov/daruma/commit/78419dddca055a1649b1626ff0835a0dcb47d799))
* **agents:** run the checks on pull requests, not locally ([c3a0b7b](https://github.com/igrybkov/daruma/commit/c3a0b7b2168b9d7d3b6f839dc50065926e2067ad))
* **architecture:** add a writing guide and scope topics by task ([97ee6e2](https://github.com/igrybkov/daruma/commit/97ee6e2b36d021c214de168056ff3d32860c16c7))
* **architecture:** let readers follow links past the first topic ([f608a93](https://github.com/igrybkov/daruma/commit/f608a93c531e7b8dc499f4e09f713d594fb28739))
* **architecture:** split ARCHITECTURE.md into topics by kind of work ([3fb3903](https://github.com/igrybkov/daruma/commit/3fb3903accdd17077bc905bbe779a6ff7af3d606))
* **architecture:** split ARCHITECTURE.md into topics by kind of work ([768c0ac](https://github.com/igrybkov/daruma/commit/768c0ac6412ef65ea50ef5fb494f2d8dc217c353))
* **blueprints:** move the blueprint list next to the blueprints ([99f505e](https://github.com/igrybkov/daruma/commit/99f505e9e7f53237b96b784f0d152dee9c980433))
* correct the persona test timings ([191b219](https://github.com/igrybkov/daruma/commit/191b21987266bb9f7ddab11ee567cc6113480de1))
* correct the persona test timings ([abd0003](https://github.com/igrybkov/daruma/commit/abd0003be559a8669941e3d9e433aeb84fcfc2d6))
* give the blueprint import badges a fixed width ([ef82ed3](https://github.com/igrybkov/daruma/commit/ef82ed35eed8b8a92602393f1e033de582fdae08))
* give the blueprint import badges a fixed width ([8183e1c](https://github.com/igrybkov/daruma/commit/8183e1cecd3bc333d7067a688c33347c53054464))
* make the blueprint import badges larger ([e968af2](https://github.com/igrybkov/daruma/commit/e968af2bbb2f751d9fad29be1b301e37b46f7922))
* **packages:** say what a package is and why the device uses them ([14cdbb4](https://github.com/igrybkov/daruma/commit/14cdbb4bb4d0111507d421ab46689467cfe6c21b))
* re-record the demos with the real menu and touch marks ([ba8bf38](https://github.com/igrybkov/daruma/commit/ba8bf38c1c680c3f5322d958c634395c42101faf))
* **readme:** add a table of app and card screens ([a6727f3](https://github.com/igrybkov/daruma/commit/a6727f31e01caf3f7126de3f4474aed529d2f79b))
* **readme:** add a table of app and card screens ([50a4586](https://github.com/igrybkov/daruma/commit/50a45864701c28152222c287bd046e5de7a07e36))
* **readme:** lead with what Daruma is and move the pitch lower ([c0acb1c](https://github.com/igrybkov/daruma/commit/c0acb1cec03a4531619b4926808cd0f34f70bec0))
* rewrite the README intro and run checks on pull requests ([2e57d63](https://github.com/igrybkov/daruma/commit/2e57d63e20585db8a47b055b4c0646bb5c725bfd))
* run the screen tests in parallel ([295f48c](https://github.com/igrybkov/daruma/commit/295f48c013a22796c37d5fd6bcb272a4e91a8c9c))
* show the blueprint import badges at their own size ([25ff651](https://github.com/igrybkov/daruma/commit/25ff6517e641bb2d2eedd640815af033b0a4c4fa))
* show the device at work at the top of the README ([7276102](https://github.com/igrybkov/daruma/commit/727610229e2c91db0471951482726966e1fbfa9e))
* show the device at work at the top of the README ([50c1ea2](https://github.com/igrybkov/daruma/commit/50c1ea222a8e8065535f4db02eab754eb02cc4bd))
* the screen tests run on macOS and Linux ([cd31025](https://github.com/igrybkov/daruma/commit/cd31025a2527558b6217a3b7a2ae3f67ad1d80a0))
* use the make goals in the contributor docs ([c3fdbce](https://github.com/igrybkov/daruma/commit/c3fdbce67f753404812647032ee74c9df5210782))
* write the folder READMEs for a reader new to Daruma ([2916f0b](https://github.com/igrybkov/daruma/commit/2916f0b30696bbdc5381329bccfcc33c7626e203))

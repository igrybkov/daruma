#pragma once

// Daruma hub. Owns the device's state (mood, activities, reactions), the
// shared signals, the personas, input routing and the plug-in points modules
// use: apps, menu items, layers, screens, input handlers and named actions.
// Core never needs to know which modules exist.
//
// Mood logic is based on https://github.com/FamousWolf/daruma (MIT).

#include <functional>
#include <map>
#include <string>
#include <vector>

#include "esphome/components/display/display.h"
#include "esphome/components/number/number.h"
#include "esphome/core/color.h"
#include "esphome/core/component.h"
#include "persona.h"
#include "card_queue.h"
#include "sound_gate.h"
#include "focus.h"
#include "gesture.h"
#include "ha_calls.h"
#include "layout.h"
#include "module.h"
#include "profile.h"
#include "signals.h"
#include "state_machine.h"
#include "states.h"

namespace Daruma {

// What the menu, apps and other screens get. Bindings act on the device's own
// screen; once a screen is open, gestures arrive here instead. Touch gestures
// carry the point (x, y); navigation from buttons or a knob carries -1, -1.
enum class Input {
  TAP,         // short tap on the screen (x, y set)
  HOLD,        // hold on the screen
  LONG_HOLD,   // long hold on the screen
  SWIPE_LEFT,  // quick flick across the screen (x, y = where it started)
  SWIPE_RIGHT,
  SWIPE_UP,
  SWIPE_DOWN,
  STROKE,  // finger rubbed back and forth, like petting
  BACK,    // navigation: one level back (the board's `back` input)
  CLOSE,   // navigation: close it all
  NEXT,    // navigation without touch: move the focus on
  PREV,
  SELECT,
  DISMISS,  // close transient UI (sent to every handler)
};

// A button in the menu dock: a colored circle with an icon, the label under it.
struct MenuItem {
  std::string label;
  // A Material Design Icons glyph (UTF-8), or short plain text such as "25".
  std::string icon;
  esphome::Color background;
  esphome::Color foreground;
  std::function<void()> action;
  // When set, tapping the item opens this page instead of running action.
  std::string submenu_title;
  std::vector<MenuItem> submenu;
  // Set by the hub's named menus instead of an action: open this app, this
  // menu, or the app board (`board`). The menu acts on them.
  std::string app;
  std::string menu;
  bool board{false};

  static MenuItem make(const std::string &label, const std::string &icon, esphome::Color background,
                       esphome::Color foreground, std::function<void()> action) {
    MenuItem item;
    item.label = label;
    item.icon = icon;
    item.background = background;
    item.foreground = foreground;
    item.action = std::move(action);
    return item;
  }
};

// Where an app draws: its area of the screen, the persona's theme and fonts.
struct AppView {
  esphome::display::Display &display;
  const Theme &theme;
  int x, y, w, h;                     // The app area (Layout::content); draw inside it.
  esphome::display::BaseFont *text;   // Names, numbers.
  esphome::display::BaseFont *small;  // Labels, captions.
  esphome::display::BaseFont *icons;  // Material Design Icons.
  // The screen's layout: px() scales a 320x240 design size to this screen.
  const Layout *layout{nullptr};
  // The board moves a focus with buttons (no touch): draw the app's focused
  // item with a ring in theme.focus_color().
  bool focus{false};

  int px(float v) const { return this->layout != nullptr ? this->layout->px(v) : (int) v; }
  Rect area() const { return Rect{this->x, this->y, this->w, this->h}; }
};

// A full-screen app on the menu's app board (Stats, Tasks, ...). Modules add
// their own; the device yaml's `apps:` list sets the board order, and each
// app gets an "App: <Name>" switch in HA. A theme may show an app under
// another name or icon.
struct App {
  std::string id;    // Stable key, used by themes and the apps: list: "stats".
  std::string name;  // Default name: "Stats".
  std::string icon;  // Default Material Design Icons glyph.
  esphome::Color color;
  // One short line under the name on the board ("Streak 5"). Optional.
  std::function<std::string()> status;
  // The header title while open, when it should differ from the name. Optional.
  std::function<std::string()> title;
  std::function<void(AppView &)> draw;
  // Taps and swipes inside the app area, in app-area coordinates. Return
  // true when the app used it. Optional.
  //
  // Boards without touch send NEXT, PREV and SELECT (x = y = -1). An app
  // that moves its own focus (Tasks: rows) or pages (Calendar: days) takes
  // them here. When it returns false for NEXT or PREV, the menu sends
  // SWIPE_UP or SWIPE_DOWN instead, so a scrolling app needs no extra code.
  std::function<bool(Input, int, int)> input;
  // The app came on screen / left it. Fetch only while open. Optional.
  std::function<void()> on_open;
  std::function<void()> on_close;
  // Back (the header arrow or the board's back input) while the app is
  // open. Return true when the app took it to leave an inner view, such as
  // Calendar's day view; false lets the menu close the app. Optional.
  std::function<bool()> back;
  // The app's switch in HA turned it on or off. Off: it is off the board
  // and should stop fetching. Optional.
  std::function<void(bool)> on_enable;
  bool enabled{true};
};

// A gesture on a named input, before bindings see it. Filters (the ringing
// alarm, a message bubble) may take it first.
struct GestureEvent {
  const std::string &input;
  Gesture gesture;
  bool touch;
  int x, y;
};

using Layer = std::function<void(esphome::display::Display &)>;
// Returns true when it drew the whole screen (the persona and layers are skipped).
using Screen = std::function<bool(esphome::display::Display &)>;
// Returns true when it consumed the input.
using InputHandler = std::function<bool(Input, int, int)>;
using GestureFilter = std::function<bool(const GestureEvent &)>;
using MenuProvider = std::function<void(std::vector<MenuItem> &)>;
// An action with an argument: `menu.open:quick` runs "menu.open" with "quick".
using ArgAction = std::function<void(const std::string &)>;

// One item of a named menu, as the build resolved it (registry.resolve_menus).
struct MenuEntry {
  enum Kind : uint8_t { MODULE, APP, ACTION, MORE, MENU, EVENT };
  Kind kind;
  std::string id;     // Module, app, action, menu or event name.
  std::string label;  // Actions, menus and events.
  std::string icon;
  std::string color;  // A theme key or "RRGGBB"; "" for the theme's edge.
};
using TitleProvider = std::function<std::string()>;
using Action = std::function<void()>;
// An action's menu button for the moment. It gets the build's look
// (label, icon, color) and may change it, or give it a submenu. False hides
// the button: the action makes no sense now (Break during a focus).
using ActionButton = std::function<bool(MenuItem &)>;
// Where a part of the device's own screen is now; empty while it is hidden.
using AreaProvider = std::function<Rect()>;

class Hub : public esphome::Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  // Modules set up before the on_boot automations and the first draw.
  float get_setup_priority() const override { return 850.0f; }

  // --- Modules ------------------------------------------------------------
  void add_module(Module *module) { this->modules_.push_back(module); }

  // --- State: reaction > top activity > mood -------------------------------
  // The state shown now.
  StateId state();
  StateId mood() const { return this->mood_; }
  // An activity owned by `owner` (one each), on top of the stack. Plays the
  // persona's sound for it unless `sound` is false.
  void set_activity(const std::string &owner, StateId activity, bool sound = true);
  void clear_activity(const std::string &owner);
  // True when any owner holds this activity, on top or under others.
  bool holds_activity(StateId activity) const { return this->machine_.holds(activity); }
  // A one-shot reaction: its animation for `ms` (0 = the registry's
  // duration), and its sound and words. A duration of 0 in the registry
  // means sound only.
  void react(StateId reaction, uint32_t ms = 0);
  // The current persona's sound for a state ("" for none).
  std::string sound_for(StateId state) const;
  // Plays a sound by name (core sets the player: the sounds switch and the
  // audio guards live there) and shows words in the speech bubble.
  void set_sound_player(std::function<void(const std::string &)> player) { this->sound_player_ = std::move(player); }
  // Plays a sound by name through that player, which skips it when the
  // Sounds switch is off or the speaker is busy. "" plays nothing. An
  // urgent sound plays even when Sounds is off because of a hold (see
  // set_sounds_held()).
  void play_sound(const std::string &name, bool urgent = false) {
    if (name.empty() || !this->sound_player_)
      return;
    this->urgent_sound_ = urgent;
    this->sound_player_(name);
    this->urgent_sound_ = false;
  }
  // A module turned Sounds off for a while (Do not disturb), not the person.
  void set_sounds_held(bool held) { this->sounds_held_ = held; }
  // The player's guard: may the sound it got now play, with the Sounds
  // switch at `sounds_on`? Valid only during the player call.
  bool sound_allowed(bool sounds_on) const { return sound_passes(sounds_on, this->sounds_held_, this->urgent_sound_); }

  // --- Mood ---------------------------------------------------------------
  bool sleepy{false};
  bool sleeping{false};
  void set_happiness(int value, bool update_last_change = true, bool publish = true);
  void add_happiness(int delta, bool update_last_change = true);
  int get_happiness() const { return this->happiness_; }
  void decay_happiness();
  // A mood by name, any case; "Auto" (or "") returns control to the mood logic.
  void force_mood(const std::string &mood);
  void reset_reactions();
  void set_happiness_meter(esphome::number::Number *meter) { this->happiness_meter_ = meter; }
  // Mic off, by the switch or in hardware. The device sleeps while it lasts.
  void set_mute(bool muted);
  void set_hardware_mute(bool muted);
  bool muted() const { return this->mute_ || this->hardware_mute_; }
  // Asleep on purpose (quiet hours): the mood stays sleeping while it lasts.
  void set_asleep(bool asleep);

  // --- Message bubble -----------------------------------------------------------
  void show_message(const std::string &text, int seconds);
  void clear_message();
  const std::string &message() const { return this->message_; }

  // --- Cards: messages and info prompts from Home Assistant ------------------
  // A module holds them back while its test is true (Do not disturb). The
  // prompts module asks holds_cards() too. When the hold ends, the waiting
  // cards show one by one, oldest first, within card_limits().
  void add_card_hold(std::function<bool()> hold) { this->card_holds_.push_back(std::move(hold)); }
  bool holds_cards() const;
  void set_card_limits(CardLimits limits) { this->card_limits_ = limits; }
  const CardLimits &card_limits() const { return this->card_limits_; }
  // A message from HA: shows now with the `notify` chime, or waits while
  // cards are held. "" clears the bubble at once.
  void post_message(const std::string &text, int seconds);
  size_t messages_waiting() const { return this->card_queue_.size(); }

  // --- Activity ----------------------------------------------------------------
  // The last input, prompt or HA message, in millis(). The screen dims
  // when nothing happened for a while. The bubble's own words don't count.
  void poke();
  uint32_t last_activity() const { return this->last_activity_; }

  // --- Personas --------------------------------------------------------------
  void add_persona(Persona *persona);
  bool set_persona(const std::string &name);
  Persona *persona() const { return this->persona_; }

  void blink();
  void wink();
  void look_around();

  // --- Shared signals -----------------------------------------------------------
  const Signals &signals() const { return this->signals_; }
  // Progress, 0..10, from named sources. The value shown is their weighted
  // average; `behind` from any of them. HA can take it over (override).
  void add_progress_source(const std::string &name, float weight);
  void set_progress(const std::string &source, float value, bool behind = false);
  void set_progress_override(bool on);
  void set_custom_progress(int value, bool behind);
  // 0..10, or -1 for unset.
  void set_wellbeing(int value);
  // "Clear", "Cloudy", "Rain", "Snow" or "Night".
  void set_sky(const std::string &sky);
  void set_hour(int hour);
  // 1 = Sunday .. 7 = Saturday.
  void set_weekday(int weekday);
  // Where today's goal stands. With `announce`, a move up plays the `paint`
  // reaction, if the persona has a look of its own for it. Restoring at boot,
  // the midnight reset and setting changes stay quiet.
  void set_goal(Goal goal, bool announce = false);

  // --- Screen ----------------------------------------------------------------
  // The display the hub draws on. Its size sets the layout (at setup).
  void set_display(esphome::display::Display *display) { this->display_ = display; }
  esphome::display::Display *display() const { return this->display_; }
  // Regions for this screen size (see layout.h).
  const Layout &layout() const { return this->layout_; }
  // What the screen can do (the board's display_profile).
  void set_profile(int colors, bool animate, uint32_t min_frame_ms, bool partial_refresh, uint16_t full_refresh_every);
  const DisplayProfile &profile() const { return this->scheduler_.profile(); }
  // The board has touch input.
  bool has_touch() const { return this->touch_input_ >= 0; }
  // The board moves a focus with NEXT and PREV (buttons or a knob). Menus,
  // apps and prompts then draw a focus ring.
  bool uses_focus() const;

  // --- Drawing ------------------------------------------------------------
  // Frames are paced by a scheduler (profile.h): the hub's loop draws when
  // something asked for a frame, no closer together than min_frame.
  // request_frame(): draw soon, even while the gate holds motion back (a
  // voice phase changed). request_redraw(): the idle screen changed; drawn
  // while the gate allows.
  void request_frame() { this->scheduler_.invalidate(); }
  // Core's rule for when the idle screen may move (no voice phase up).
  void set_frame_gate(std::function<bool()> gate) { this->frame_gate_ = std::move(gate); }
  // The idle screen may move now: the frame gate holds no motion back.
  bool motion_open() const { return !this->frame_gate_ || this->frame_gate_(); }
  // The frame being drawn repaints everything (no partial refresh now).
  bool full_frame() const { return this->full_frame_; }
  // The whole screen: core sets how (voice phases, idle). The board's
  // display lambda calls render().
  void set_renderer(std::function<void(esphome::display::Display &)> renderer) {
    this->renderer_ = std::move(renderer);
  }
  void render(esphome::display::Display &display);
  // Idle screen: first screen that claims it, else the persona plus layers.
  void draw_idle(esphome::display::Display &display, float look_y);
  // Cheap idle update when only the persona moved: the persona repaints just the
  // changed pixels. Returns false when a full draw_idle() is needed.
  bool draw_idle_delta(esphome::display::Display &display);
  // Still frame for a voice phase (listening, offline, ...).
  void draw_still(esphome::display::Display &display, StateId state);
  // The persona for the current state, into the stage: animated, or its still
  // frame when the profile does not animate. For screens drawn over the
  // persona (the menu dock).
  void draw_persona(esphome::display::Display &display, float look_y = 0.0f);
  // Lower order draws first (further back).
  void add_layer(int order, Layer layer);
  // Higher priority is asked first.
  void add_screen(int priority, Screen screen);
  void request_redraw() { this->dirty_ = true; }
  // A layer changed only inside `area` and paints all of it opaque: the
  // next idle frame draws the layers clipped to it, and leaves the persona
  // and the rest of the screen alone. Use request_redraw() when the layer
  // shrinks or goes away, since the persona must show again under it.
  void request_area(const Rect &area) { this->area_ = this->area_.united(area); }

  // --- Info line -------------------------------------------------------------
  // A thin line of short text on the device's own screen: layout().info, or
  // info_top when the persona's theme says so (theme.py `info_line`). The
  // module that draws it marks it used while it may show anything. The
  // bottom corners always keep clear of it (Layout::corner_bottom).
  void set_info_line_used(bool used) {
    if (used != this->info_used_) {
      this->info_used_ = used;
      this->dirty_ = true;
    }
  }
  // Where the line goes for the current persona; empty when unused or off.
  // A mark takes the right end of it (set_info_mark()).
  Rect info_line() const;
  // A small square at the right end of the info line's place, for a status
  // mark (Do not disturb). Shown even when no module uses the line.
  void set_info_mark(bool on) {
    if (on != this->info_mark_) {
      this->info_mark_ = on;
      this->dirty_ = true;
    }
  }
  bool info_mark_on() const { return this->info_mark_; }
  Rect info_mark() const;
  bool needs_redraw();

  // --- Home Assistant calls that wait for a reply ------------------------------------
  // Every homeassistant.action with capture_response, on_success or on_error
  // goes through ha_calls().call(); its on_success and on_error call
  // ha_calls().done(token). See ha_calls.h for why.
  HaCalls &ha_calls() { return this->ha_calls_; }
  // True while HA is connected and subscribed (core sets it).
  void set_ha_link(std::function<bool()> link) { this->ha_link_ = std::move(link); }
  bool ha_linked() const { return this->ha_link_ && this->ha_link_(); }

  // What is due at `now`: a frame to draw, an HA call to send or an answer
  // to wait for. Empty when nothing is. A test runner waits for that before
  // the clock moves, and names what kept it waiting.
  std::string busy(uint32_t now);

  // --- Actions ----------------------------------------------------------------------
  // Named actions ("pomodoro.toggle") that bindings run. Modules add them.
  void add_action(const std::string &name, Action action) { this->actions_[name] = std::move(action); }
  // An action that takes an argument after a colon: "menu.open:quick".
  void add_arg_action(const std::string &name, ArgAction action) { this->arg_actions_[name] = std::move(action); }
  bool has_action(const std::string &name) const;
  bool run_action(const std::string &name);
  std::vector<std::string> action_names() const;
  // How the action's button looks now, in menus that list it (see ActionButton).
  void set_action_button(const std::string &name, ActionButton button) {
    this->action_buttons_[name] = std::move(button);
  }

  // --- Tap areas ------------------------------------------------------------------
  // A part of the device's own screen that leads somewhere: the pomodoro
  // plaque, the temperature badge, the next event line. The module that
  // draws it names it and says where it is now. What a tap on it does comes
  // from the build (`targets:`, checked by registry.resolve_targets): an
  // action, `menu.open:<menu>` or `menu.app:<app>`. A tap on the persona
  // outside every area goes to the bindings as before.
  void add_tap_area(const std::string &name, AreaProvider area) { this->areas_[name].area = std::move(area); }
  void add_tap_target(const std::string &area, const std::string &action) { this->areas_[area].action = action; }
  // The action for a tap at (x, y) on the device's own screen; "" for none.
  std::string tap_target_at(int x, int y) const;

  // --- Inputs (declared by the board) -----------------------------------------------
  int add_input(const std::string &name, bool touch, uint32_t double_ms, uint32_t hold_ms, uint32_t long_hold_ms);
  void add_navigation(int input, Gesture gesture, Input nav);
  int add_binding(int input, Gesture gesture, const std::string &action, bool idle_only);
  void set_binding_action(int binding, const std::string &action);
  const std::string &binding_action(int binding) const { return this->bindings_[binding].action; }
  // A button input changed state.
  void button_edge(int input, bool pressed);
  // A menu, app or prompt is open: gestures navigate it, idle bindings rest.
  void set_ui_open(bool open) { this->ui_open_ = open; }
  // A prompt is on screen. Kept apart from set_ui_open, so the menu closing
  // under a prompt leaves the prompt's input alone.
  void set_prompt_open(bool open) { this->prompt_open_ = open; }
  bool ui_open() const { return this->ui_open_ || this->prompt_open_; }
  bool prompt_open() const { return this->prompt_open_; }
  // The last idle frame showed a screen (the menu, a prompt), not the persona.
  bool screen_shown() const { return this->screen_shown_; }
  // Higher priority is asked first. True takes the gesture.
  void add_gesture_filter(int priority, GestureFilter filter);
  // Higher priority is asked first.
  void add_input_handler(int priority, InputHandler handler);
  bool dispatch(Input input, int x = -1, int y = -1);

  // --- Touch ----------------------------------------------------------------------
  // The screen input's finger: start on touch, move on every update, end on
  // release. Taps, holds, swipes and strokes come out of these.
  void touch_start(int x, int y);
  void touch_move(int x, int y);
  void touch_end();
  // The touch going on, or the last one. A tap reaches the input handlers
  // at the point where the finger came down; this tells them the rest.
  const TouchTrack &last_touch() const { return this->touch_.track(); }

  // --- Menu content -----------------------------------------------------------
  // Lower order comes first. A provider belongs to the module whose setup()
  // adds it; a menu that lists the module shows its items.
  void add_menu_provider(int order, MenuProvider provider);
  void set_menu_title(TitleProvider provider) { this->menu_title_ = std::move(provider); }
  // Every provider's items, in order.
  std::vector<MenuItem> menu_items();
  // Named menus (daruma: menus:, checked by the build).
  void add_menu_entry(const std::string &menu, uint8_t kind, const std::string &id, const std::string &label,
                      const std::string &icon, const std::string &color);
  bool has_menu(const std::string &menu) const { return this->menus_.count(menu) != 0; }
  // A menu's buttons now: module items for the moment, apps that are on,
  // actions, other menus and the app board. Empty for an unknown menu.
  std::vector<MenuItem> menu_items(const std::string &menu);
  // A menu's event button was pressed: fire esphome.daruma_menu in HA, with the event's name.
  void set_event_sender(std::function<void(const std::string &)> sender) { this->event_sender_ = std::move(sender); }
  std::string menu_title();

  // --- Apps -----------------------------------------------------------------------
  void add_app(App app) { this->apps_.push_back(std::move(app)); }
  // The board order, from the device yaml's apps: list.
  void set_app_order(std::vector<std::string> order) { this->app_order_ = std::move(order); }
  // Apps switched on, in board order.
  std::vector<App *> apps();
  App *find_app(const std::string &id);
  void set_app_enabled(const std::string &id, bool enabled);
  // The current persona's theme (the default one with no persona).
  const Theme &theme() const { return this->persona_ != nullptr ? this->persona_->theme() : default_theme(); }

 protected:
  StateId compute_mood_();
  bool has_happiness_changed_(uint32_t ms) const;
  bool has_mood_changed_(uint32_t ms) const;
  void started_(StateId state);  // Plays the persona's sound and words for a state.
  void update_progress_();

  struct InputSlot {
    std::string name;
    bool touch;
    PressRecognizer press;
  };
  struct BindingSlot {
    int input;
    Gesture gesture;
    std::string action;
    bool idle_only;
  };
  struct NavSlot {
    int input;
    Gesture gesture;
    Input nav;
  };
  uint16_t bound_mask_(int input) const;
  void emit_(int input, Gesture gesture, int x, int y);

  template<typename T> struct Ordered {
    int order;
    T value;
  };
  template<typename T> static void insert_sorted_(std::vector<Ordered<T>> &list, int order, T value, bool descending);

  std::vector<Module *> modules_;
  StateMachine machine_;
  StateId mood_{static_cast<StateId>(0)};
  StateId forced_mood_{static_cast<StateId>(0)};
  bool has_forced_mood_{false};
  std::function<void(const std::string &)> sound_player_;

  int happiness_{0};
  bool init_in_progress_{true};
  uint32_t last_happiness_change_{0};
  uint32_t last_mood_change_{0};
  esphome::number::Number *happiness_meter_{nullptr};
  bool mute_{false};
  bool hardware_mute_{false};
  bool asleep_{false};
  bool sounds_held_{false};
  bool urgent_sound_{false};

  std::string message_;
  uint32_t message_until_{0};
  std::vector<std::function<bool()>> card_holds_;
  CardLimits card_limits_;
  CardQueue card_queue_;
  uint32_t last_activity_{0};
  void show_card_(const std::string &text, int seconds);

  std::vector<Persona *> personas_;
  Persona *persona_{nullptr};
  Signals signals_;
  struct ProgressSource {
    std::string name;
    float weight;
    float value{-1};
    bool behind{false};
  };
  std::vector<ProgressSource> progress_;
  bool progress_override_{false};
  int custom_progress_{0};
  bool custom_behind_{false};

  std::function<void(esphome::display::Display &)> renderer_;
  std::vector<Ordered<Layer>> layers_;
  std::vector<Ordered<Screen>> screens_;
  std::vector<Ordered<InputHandler>> input_handlers_;
  std::vector<Ordered<GestureFilter>> filters_;
  struct OwnedProvider {
    std::string module;
    MenuProvider provider;
  };
  std::vector<Ordered<OwnedProvider>> menu_providers_;
  std::map<std::string, std::vector<MenuEntry>> menus_;
  std::function<void(const std::string &)> event_sender_;
  // The module whose setup() runs now, so its providers carry its name.
  std::string setting_up_;
  TitleProvider menu_title_;
  std::vector<App> apps_;
  std::vector<std::string> app_order_;

  std::map<std::string, Action> actions_;
  std::map<std::string, ArgAction> arg_actions_;
  std::map<std::string, ActionButton> action_buttons_;
  struct TapArea {
    AreaProvider area;
    std::string action;
  };
  std::map<std::string, TapArea> areas_;
  HaCalls ha_calls_;
  // A frame should be drawn at `now` (see loop()).
  bool frame_due_(uint32_t now);
  std::function<bool()> ha_link_;
  std::vector<InputSlot> inputs_;
  std::vector<BindingSlot> bindings_;
  std::vector<NavSlot> navigation_;
  int touch_input_{-1};
  bool ui_open_{false};
  bool prompt_open_{false};

  TouchTracker touch_;

  void apply_layout_(int width, int height);

  esphome::display::Display *display_{nullptr};
  Layout layout_;
  FrameScheduler scheduler_;
  std::function<bool()> frame_gate_;
  bool full_frame_{true};

  bool dirty_{true};
  Rect area_;  // Layers to redraw there, without the persona (request_area).
  bool info_used_{false};
  bool info_mark_{false};
  bool screen_shown_{false};
  StateId drawn_state_{static_cast<StateId>(0)};
  bool drawn_valid_{false};
};

}  // namespace Daruma

--[[
Configuration options for anilistUpdater (set in anilistUpdater.conf):

DIRECTORIES: Table or comma/semicolon-separated string. The directories the script will work on. Leaving it empty will make it work on every video you watch with mpv. Example: DIRECTORIES = {"D:/Torrents", "D:/Anime"}

EXCLUDED_DIRECTORIES: Table or comma/semicolon-separated string. Useful for ignoring paths inside directories from above. Example: EXCLUDED_DIRECTORIES = {"D:/Torrents/Watched", "D:/Anime/Planned"}

UPDATE_PERCENTAGE: Number (0-100). The percentage of the video you need to watch before it updates AniList automatically. Default is 85 (usually before the ED of a usual episode duration).

SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE: Boolean. If true, when watching episode 1 of a completed anime, set it to rewatching and update progress.

UPDATE_PROGRESS_WHEN_REWATCHING: Boolean. If true, allow updating progress for anime set to rewatching. This is for if you want to set anime to rewatching manually, but still update progress automatically.

SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT: Boolean. If true, set to COMPLETED after last episode if status was CURRENT.

SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING: Boolean. If true, set to COMPLETED after last episode if status was REPEATING (rewatching).

Keybind Configuration:
KEYBIND_UPDATE: Key combination to manually update AniList progress (default: ctrl+a)
KEYBIND_LAUNCH: Key combination to launch AniList page for current anime (default: ctrl+b)
KEYBIND_OPEN_FOLDER: Key combination to open folder containing current video (default: ctrl+d)
KEYBIND_RELOAD_CONFIG: Key combination to reload configuration (default: ctrl+shift+r)

Note: Set any keybind to empty string to disable it. Examples: "ctrl+a", "alt+u", "shift+ctrl+a", "F5"

Default Hotkeys:
- Ctrl+A: Update AniList progress
- Ctrl+B: Launch AniList page for current anime
- Ctrl+D: Open folder containing current video
- Ctrl+Shift+R: Reload configuration
]]

local utils = require 'mp.utils'
local mpoptions = require("mp.options")

local conf_name = "anilistUpdater.conf"
local script_dir = (debug.getinfo(1).source:match("@?(.*/)") or "./")

-- Try script-opts directory (sibling to scripts)
local script_opts_dir = script_dir:match("^(.-)[/\\]scripts[/\\]")

if script_opts_dir then
    script_opts_dir = utils.join_path(script_opts_dir, "script-opts")
else
    -- Fallback: try to find mpv config dir
    script_opts_dir = os.getenv("APPDATA") and utils.join_path(utils.join_path(os.getenv("APPDATA"), "mpv"), "script-opts") or
                          os.getenv("HOME") and utils.join_path(utils.join_path(utils.join_path(os.getenv("HOME"), ".config"), "mpv"), "script-opts") or
                          nil
end

local script_opts_path = script_opts_dir and utils.join_path(script_opts_dir, conf_name) or nil

-- Try script directory
local script_path = utils.join_path(script_dir, conf_name)

-- Try mpv config directory
local mpv_conf_dir = os.getenv("APPDATA") and utils.join_path(os.getenv("APPDATA"), "mpv") or os.getenv("HOME") and
                         utils.join_path(utils.join_path(os.getenv("HOME"), ".config"), "mpv") or nil
local mpv_conf_path = mpv_conf_dir and utils.join_path(mpv_conf_dir, conf_name) or nil

local conf_paths = {script_opts_path, script_path, mpv_conf_path}

local default_conf = [[
# Use 'yes' or 'no' for boolean options below
# Example for multiple directories (comma or semicolon separated):
# DIRECTORIES=D:/Torrents,D:/Anime
# or
# DIRECTORIES=D:/Torrents;D:/Anime
DIRECTORIES=
EXCLUDED_DIRECTORIES=
UPDATE_PERCENTAGE=85
SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE=no
UPDATE_PROGRESS_WHEN_REWATCHING=yes
SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT=yes
SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING=yes

# Keybind configuration (leave empty to disable a keybind)
# Examples: ctrl+a, alt+u, shift+ctrl+a, F5, etc.
KEYBIND_UPDATE=ctrl+a
KEYBIND_LAUNCH=ctrl+b
KEYBIND_OPEN_FOLDER=ctrl+d
KEYBIND_RELOAD_CONFIG=ctrl+shift+r
]]

-- Try to find config file
local conf_path = nil
for _, path in ipairs(conf_paths) do
    if path then
        local f = io.open(path, "r")
        if f then
            f:close()
            conf_path = path
            -- print("Found config at: " .. path)
            break
        end
    end
end

-- If not found, try to create in order
if not conf_path then
    for _, path in ipairs(conf_paths) do
        if path then
            local f = io.open(path, "w")
            if f then
                f:write(default_conf)
                f:close()
                conf_path = path
                print("Created config at: " .. path)
                break
            end
        end
    end
end

-- If still not found or created, warn and use defaults
if not conf_path then
    mp.msg.warn("Could not find or create anilistUpdater.conf in any known location! Using default options.")
end

local function normalize_path(p)
    p = p:gsub("\\", "/")
    if p:sub(-1) == "/" then
        p = p:sub(1, -2)
    end
    return p
end

-- Function to parse and normalize directory options
local function parse_directories(dirs_string)
    if type(dirs_string) == "string" and dirs_string ~= "" then
        local dirs = {}
        for dir in string.gmatch(dirs_string, "([^,;]+)") do
            local trimmed = (dir:gsub("^%s*(.-)%s*$", "%1"):gsub('[\'"]', '')) -- trim
            table.insert(dirs, normalize_path(trimmed))
        end
        return dirs
    else
        return {}
    end
end

-- Function to load and parse configuration options
local function load_and_parse_options()
    local opts = {
        DIRECTORIES = "",
        EXCLUDED_DIRECTORIES = "",
        UPDATE_PERCENTAGE = 85,
        SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE = false,
        UPDATE_PROGRESS_WHEN_REWATCHING = true,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT = true,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING = true,
        KEYBIND_UPDATE = "ctrl+a",
        KEYBIND_LAUNCH = "ctrl+b",
        KEYBIND_OPEN_FOLDER = "ctrl+d",
        KEYBIND_RELOAD_CONFIG = "ctrl+shift+r"
    }
    
    if conf_path then
        mpoptions.read_options(opts, "anilistUpdater")
    end
    
    -- Parse directory strings into arrays
    opts.DIRECTORIES = parse_directories(opts.DIRECTORIES)
    opts.EXCLUDED_DIRECTORIES = parse_directories(opts.EXCLUDED_DIRECTORIES)
    
    return opts
end

-- Wrapper functions for keybinds
local function force_update()
    update_anilist("update")
end

local function force_anilist_update()
    update_anilist("launch")
end

local function open_in_file_browser()
    open_folder()
end

-- Function to register keybinds based on configuration
local function register_keybinds(opts)
    -- Only register keybinds if they are not empty
    if opts.KEYBIND_UPDATE ~= "" then
        mp.add_key_binding(opts.KEYBIND_UPDATE, "force_update", force_update)
    end
    
    if opts.KEYBIND_LAUNCH ~= "" then
        mp.add_key_binding(opts.KEYBIND_LAUNCH, "force_anilist_update", force_anilist_update)
    end
    
    if opts.KEYBIND_OPEN_FOLDER ~= "" then
        mp.add_key_binding(opts.KEYBIND_OPEN_FOLDER, "open_in_file_browser", open_in_file_browser)
    end
    
    if opts.KEYBIND_RELOAD_CONFIG ~= "" then
        mp.add_key_binding(opts.KEYBIND_RELOAD_CONFIG, "reload_config", reload_config)
    end
end

-- Function to reload configuration
local function reload_config()
    mp.osd_message("Reloading anilistUpdater configuration", 2)
    
    -- Load and parse new configuration
    local new_opts = load_and_parse_options()
    
    -- Update global options
    update_globals_from_options(new_opts)
    
    -- Clear existing keybinds
    mp.remove_key_binding("force_update")
    mp.remove_key_binding("force_anilist_update")
    mp.remove_key_binding("open_in_file_browser")
    mp.remove_key_binding("reload_config")
    
    -- Re-register keybinds with new configuration
    register_keybinds(options)
    
    mp.osd_message("Configuration reloaded successfully", 2)
end

-- Function to update global variables from options
local function update_globals_from_options(opts)
    options = opts
    DIRECTORIES = opts.DIRECTORIES
    EXCLUDED_DIRECTORIES = opts.EXCLUDED_DIRECTORIES
    UPDATE_PERCENTAGE = tonumber(opts.UPDATE_PERCENTAGE) or 85
    
    -- Update python_options_json
    local new_python_options = {
        SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE = opts.SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE,
        UPDATE_PROGRESS_WHEN_REWATCHING = opts.UPDATE_PROGRESS_WHEN_REWATCHING,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT = opts.SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING = opts.SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING
    }
    python_options_json = utils.format_json(new_python_options)
    
    -- Register keybinds with the updated options
    register_keybinds(opts)
end

-- Initial configuration load
local options = load_and_parse_options()
update_globals_from_options(options)

local function path_starts_with_any(path, directories)
    local norm_path = normalize_path(path)
    for _, dir in ipairs(directories) do
        if norm_path:sub(1, #dir) == dir then
            return true
        end
    end
    return false
end

function callback(success, result, error)
    if result.status == 0 then
        mp.osd_message("Operation completed successfully.", 4)
    else
        mp.osd_message("Operation failed. Check console for details.", 4)
    end
end

local function get_python_command()
    local os_name = package.config:sub(1, 1)
    if os_name == '\\' then
        -- Windows
        return "python"
    else
        -- Linux
        return "python3"
    end
end

local function get_path()
    local directory = mp.get_property("working-directory")
    -- It seems like in Linux working-directory sometimes returns it without a "/" at the end
    directory = (directory:sub(-1) == '/' or directory:sub(-1) == '\\') and directory or directory .. '/'
    -- For some reason, "path" sometimes returns the absolute path, sometimes it doesn't.
    local file_path = mp.get_property("path")
    local path = utils.join_path(directory, file_path)

    if path:match("([^/\\]+)$"):lower() == "file.mp4" then
        path = mp.get_property("media-title")
    end

    return path
end

local python_command = get_python_command()

-- Make sure it doesnt trigger twice in 1 video
local triggered = false
-- Debounce state for percent-pos events
local last_percent_check_time = 0
-- Seconds between handling percent-pos changes (below threshold)
local PERCENT_POS_DEBOUNCE = 0.5

-- Function to check if we've reached the user-defined percentage of the video
function check_progress()
    if triggered then
        return
    end
    local percent_pos = mp.get_property_number("percent-pos")
    if not percent_pos then
        return
    end

    if percent_pos >= UPDATE_PERCENTAGE then
        update_anilist("update")
        triggered = true
        return
    end

    local now = mp.get_time()
    if (now - last_percent_check_time) < PERCENT_POS_DEBOUNCE then
        return
    end
    last_percent_check_time = now
end

-- Function to launch the .py script
function update_anilist(action)
    if action == "launch" then
        mp.osd_message("Launching AniList", 2)
    end
    local script_dir = debug.getinfo(1).source:match("@?(.*/)")

    local path = get_path()

    local table = {}
    table.name = "subprocess"
    table.args = {python_command, script_dir .. "anilistUpdater.py", path, action, python_options_json}
    local cmd = mp.command_native_async(table, callback)
end

mp.observe_property("percent-pos", "number", check_progress)

-- Reset triggered
mp.register_event("file-loaded", function()
    triggered = false
    last_percent_check_time = 0
    if #DIRECTORIES > 0 then
        local path = get_path()

        if not path_starts_with_any(path, DIRECTORIES) then
            mp.unobserve_property(check_progress)
        else
            -- If it starts with the directories, check if it starts with any of the excluded directories
            if #EXCLUDED_DIRECTORIES > 0 and path_starts_with_any(path, EXCLUDED_DIRECTORIES) then
                mp.unobserve_property(check_progress)
            end

        end
    end
end)

-- Open the folder that the video is
function open_folder()
    local path = mp.get_property("path")
    local directory

    if not path then
        mp.msg.warn("No file is currently playing.")
        return
    end

    if path:find('\\') then
        directory = path:match("(.*)\\")
    elseif path:find('\\\\') then
        directory = path:match("(.*)\\\\")
    else
        directory = mp.get_property("working-directory")
    end

    -- Use the system command to open the folder in File Explorer
    local args
    if package.config:sub(1, 1) == '\\' then
        -- Windows
        args = {'explorer', directory}
    elseif os.getenv("XDG_CURRENT_DESKTOP") or os.getenv("WAYLAND_DISPLAY") or os.getenv("DISPLAY") then
        -- Linux (assume a desktop environment like GNOME, KDE, etc.)
        args = {'xdg-open', directory}
    elseif package.config:sub(1, 1) == '/' then
        -- macOS
        args = {'open', directory}
    end

    mp.command_native({
        name = "subprocess",
        args = args,
        detach = true
    })
end

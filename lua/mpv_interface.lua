-- MPV event handling and UI for mpv-anilist-updater.

local utils = require 'mp.utils'
local config = require 'lua.config'
local path_utils = require 'lua.path_utils'

local M = {}

local options = {}
local python_options = {}
local python_options_json = ""
local python_command = ""
local isPaused = false
local triggered = false
local UPDATE_INTERVAL = 0.5
local progress_timer = nil

function callback(success, result, error)
    -- Can send multiple OSD messages to display
    local messages = {}
    if result and result.stdout then
        for line in result.stdout:gmatch("[^\r\n]+") do
            local msg = line:match("^OSD:%s*(.-)%s*$")
            if msg then
                table.insert(messages, msg)
            else
                print(line)
            end
        end
    end
    
    if success and result and result.status == 0 then
        if #messages == 0 then
            table.insert(messages, "Updated anime correctly.")
        elseif #messages > 0 then
            mp.osd_message(table.concat(messages, "\n"), 5)
        end
    end
end

-- Function to launch the .py script
function update_anilist(action)
    if action == "launch" then
        mp.osd_message("Launching AniList", 2)
    end
    local script_dir = debug.getinfo(1).source:match("@?(.*/)")

    local path = path_utils.get_path()

    local table = {}
    table.name = "subprocess"
    table.args = {python_command, script_dir .. "../python/main.py", path, action, python_options_json}
    table.capture_stdout = true
    local cmd = mp.command_native_async(table, callback)
end

-- Handle pause/unpause events to control the timer
function on_pause_change(name, value)
    isPaused = value
    if value then
        progress_timer:stop()
    else
        if not triggered then
            progress_timer:resume()
        end
    end
end

function M.initialize(script_dir)
    -- Load configuration
    options = config.load_config(script_dir)
    
    -- When calling Python, pass only the options relevant to it
    python_options = {
        SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE = options.SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE,
        UPDATE_PROGRESS_WHEN_REWATCHING = options.UPDATE_PROGRESS_WHEN_REWATCHING,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT = options.SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING = options.SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING,
        ADD_ENTRY_IF_MISSING = options.ADD_ENTRY_IF_MISSING
    }
    python_options_json = utils.format_json(python_options)
    
    python_command = path_utils.get_python_command()
    
    -- Initialize timer once - we control it with stop/resume
    progress_timer = mp.add_periodic_timer(UPDATE_INTERVAL, function()
        if triggered then
            return
        end
        
        local percent_pos = mp.get_property_number("percent-pos")
        if not percent_pos then
            return
        end

        if percent_pos >= options.UPDATE_PERCENTAGE then
            update_anilist("update")
            triggered = true
            if progress_timer then
                progress_timer:stop()
            end
            return
        end
    end)
    -- Start with timer stopped - it will be started when a valid file loads
    progress_timer:stop()

    -- Set up event handlers
    mp.observe_property("pause", "bool", on_pause_change)

    -- Reset triggered and start/stop timer based on file loading
    mp.register_event("file-loaded", function()
        triggered = false
        progress_timer:stop()

        if not path_utils.is_ani_cli_compatible() and #options.DIRECTORIES > 0 then
            local path = path_utils.get_path()

            if not path_utils.path_starts_with_any(path, options.DIRECTORIES) then
                mp.unobserve_property(on_pause_change)
                return
            else
                -- If it starts with the directories, check if it starts with any of the excluded directories
                if #options.EXCLUDED_DIRECTORIES > 0 and path_utils.path_starts_with_any(path, options.EXCLUDED_DIRECTORIES) then
                    mp.unobserve_property(on_pause_change)
                    return
                end
            end
        end

        -- Start timer for this file
        if not isPaused then
            progress_timer:resume()
        end
    end)

    -- Default keybinds - can be customized in input.conf using script-binding commands
    mp.add_key_binding("ctrl+a", 'update_anilist', function()
        update_anilist("update")
    end)

    mp.add_key_binding("ctrl+b", 'launch_anilist', function()
        update_anilist("launch")
    end)

    mp.add_key_binding("ctrl+d", 'open_folder', path_utils.open_folder)
end

return M

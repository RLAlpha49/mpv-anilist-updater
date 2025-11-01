-- MPV event handling and UI for mpv-anilist-updater.

local utils = require 'mp.utils'
local config = require 'lua.config'
local path_utils = require 'lua.path_utils'

local M = {}

local options = {}
local python_options = {}
local python_options_json = ""
local python_command = ""
local script_directory = ""
local isPaused = false
local triggered = false
local UPDATE_INTERVAL = 0.5
local progress_timer = nil

function callback(success, result, error)
    -- Collect OSD messages from stdout
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

    -- Collect stderr for logging purposes
    if result and result.stderr then
        for line in result.stderr:gmatch("[^\r\n]+") do
            print(line)
        end
    end

    -- Display OSD message(s)
    if #messages > 0 then
        mp.osd_message(table.concat(messages, "\n"), 5)
    elseif result and result.status ~= 0 then
        -- If there was an error but no OSD message, show generic error
        mp.osd_message("Error: Update failed. Check console for details.", 3)
    elseif success and result and result.status == 0 then
        -- Success with no specific message
        mp.osd_message("Updated anime correctly.", 5)
    end
end

-- Function to launch the .py script
function update_anilist(action)
    if action == "launch" then
        mp.osd_message("Launching AniList", 2)
    end

    local path = path_utils.get_path()

    local python_script_path = utils.join_path(script_directory, "python")
    python_script_path = utils.join_path(python_script_path, "main.py")

    local table = {}
    table.name = "subprocess"
    table.args = {python_command, python_script_path, path, action, python_options_json}
    table.capture_stdout = true
    table.capture_stderr = true
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
    script_directory = script_dir

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
        -- Always stop timer first to ensure clean state
        if progress_timer then
            progress_timer:stop()
        end

        if not path_utils.is_ani_cli_compatible() and #options.DIRECTORIES > 0 then
            local path = path_utils.get_path()

            if not path or not path_utils.path_starts_with_any(path, options.DIRECTORIES) then
                mp.unobserve_property(on_pause_change)
                return
            else
                -- If it starts with the directories, check if it starts with any of the excluded directories
                if #options.EXCLUDED_DIRECTORIES > 0 and
                    path_utils.path_starts_with_any(path, options.EXCLUDED_DIRECTORIES) then
                    mp.unobserve_property(on_pause_change)
                    return
                end
            end
        end

        -- Re-observe pause property for valid files
        mp.observe_property("pause", "bool", on_pause_change)

        -- Start timer for this file only if not paused
        if not isPaused then
            progress_timer:resume()
        end
    end)

    -- Reset triggered and stop timer when file ends
    mp.register_event("end-file", function()
        triggered = false
        if progress_timer then
            progress_timer:stop()
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

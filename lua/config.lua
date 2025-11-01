-- Configuration management for mpv-anilist-updater.

local utils = require 'mp.utils'
local mpoptions = require("mp.options")
local path_utils = require 'lua.path_utils'

-- Module table: Contains only the functions we want to export to other modules.
-- Private helper functions (like get_mpv_config_dir, parse_directory_string) 
-- are kept local to this module and not accessible from outside.
local M = {}

-- Helper function to get MPV config directory
local function get_mpv_config_dir()
    return os.getenv("APPDATA") and utils.join_path(os.getenv("APPDATA"), "mpv") or os.getenv("HOME") and
               utils.join_path(utils.join_path(os.getenv("HOME"), ".config"), "mpv") or nil
end

-- Helper function to parse directory strings (comma or semicolon separated)
local function parse_directory_string(dir_string)
    if type(dir_string) == "string" and dir_string ~= "" then
        local dirs = {}
        for dir in string.gmatch(dir_string, "([^,;]+)") do
            local trimmed = (dir:gsub("^%s*(.-)%s*$", "%1"):gsub('[\'"]', '')) -- trim
            table.insert(dirs, path_utils.normalize_path(trimmed))
        end
        return dirs
    else
        return {}
    end
end

-- Helper function to create directory if it doesn't exist
local function create_directory_if_needed(dir_path)
    if dir_path and dir_path ~= "" then
        -- Check if directory exists by trying to rename it to itself
        local success = os.rename(dir_path, dir_path)
        if success then
            return true
        end
        
        -- Directory doesn't exist, try to create it using mp.command_native
        local os_sep = package.config:sub(1, 1)
        local args
        
        if os_sep == '\\' then
            -- Windows: use mkdir (no -p flag)
            args = {"mkdir", dir_path}
        else
            -- Unix-like: use mkdir -p
            args = {"mkdir", "-p", dir_path}
        end
        
        local res = mp.command_native({
            name = "subprocess",
            args = args,
            capture_stdout = false,
            capture_stderr = false
        })
        
        -- Check if creation was successful
        if res and (res.status == 0 or res == true) then
            return true
        end
        
        -- If creation failed, emit a warning
        mp.msg.warn("Could not create directory: " .. dir_path)
        return false
    end
    return false
end

-- Default config content
local default_conf = [[# anilistUpdater Configuration
# For detailed explanations of all available options, see:
# https://github.com/AzuredBlue/mpv-anilist-updater?tab=readme-ov-file#configuration-anilistupdaterconf

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
ADD_ENTRY_IF_MISSING=no
]]

function M.load_config(script_dir)
    local conf_name = "anilistUpdater.conf"

    -- Try script-opts directory (sibling to scripts)
    local script_opts_dir = script_dir:match("^(.-)[/\\]scripts[/\\]")

    if script_opts_dir then
        script_opts_dir = utils.join_path(script_opts_dir, "script-opts")
    else
        -- Fallback: try to find mpv config dir
        local mpv_conf_dir = get_mpv_config_dir()
        script_opts_dir = mpv_conf_dir and utils.join_path(mpv_conf_dir, "script-opts") or nil
    end

    local script_opts_path = script_opts_dir and utils.join_path(script_opts_dir, conf_name) or nil

    -- Try script directory
    local script_path = utils.join_path(script_dir, conf_name)

    -- Try mpv config directory
    local mpv_conf_dir = get_mpv_config_dir()
    local mpv_conf_path = mpv_conf_dir and utils.join_path(mpv_conf_dir, conf_name) or nil

    local conf_paths = {script_opts_path, script_path, mpv_conf_path}

    -- Try to find config file
    local conf_path = nil
    for _, path in ipairs(conf_paths) do
        if path then
            local f = io.open(path, "r")
            if f then
                f:close()
                conf_path = path
                break
            end
        end
    end

    -- If not found, try to create in order
    if not conf_path then
        for _, path in ipairs(conf_paths) do
            if path then
                -- Ensure parent directory exists
                local parent_dir = path:match("^(.-)[/\\][^/\\]*$")
                if parent_dir then
                    create_directory_if_needed(parent_dir)
                end

                local f = io.open(path, "w")
                if f then
                    f:write(default_conf)
                    f:close()
                    conf_path = path
                    break
                end
            end
        end
    end

    -- If still not found or created, warn and use defaults
    if not conf_path then
        mp.msg.warn("Could not find or create anilistUpdater.conf in any known location! Using default options.")
    end

    -- Initialize options with defaults
    local options = {
        DIRECTORIES = "",
        EXCLUDED_DIRECTORIES = "",
        UPDATE_PERCENTAGE = 85,
        SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE = false,
        UPDATE_PROGRESS_WHEN_REWATCHING = true,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT = true,
        SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING = true,
        ADD_ENTRY_IF_MISSING = false
    }

    -- Override defaults with values from config file
    if conf_path then
        mpoptions.read_options(options, "anilistUpdater")
    end

    -- Parse DIRECTORIES and EXCLUDED_DIRECTORIES using helper function
    options.DIRECTORIES = parse_directory_string(options.DIRECTORIES)
    options.EXCLUDED_DIRECTORIES = parse_directory_string(options.EXCLUDED_DIRECTORIES)

    return options
end

return M

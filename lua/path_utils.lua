-- Path handling utilities for mpv-anilist-updater.

local utils = require 'mp.utils'

local M = {}

-- Helper function to normalize path separators
function M.normalize_path(p)
    p = p:gsub("\\", "/")
    if p:sub(-1) == "/" then
        p = p:sub(1, -2)
    end
    return p
end

function M.path_starts_with_any(path, directories)
    local norm_path = M.normalize_path(path)
    for _, dir in ipairs(directories) do
        if norm_path:sub(1, #dir) == dir then
            return true
        end
    end
    return false
end

-- Helper function to detect ani-cli compatibility
function M.is_ani_cli_compatible()
    local directory = mp.get_property("working-directory") or ""
    local file_path = mp.get_property("path") or ""
    local full_path = utils.join_path(directory, file_path)

    -- Auto-detect ani-cli compatibility by checking for http:// or https:// anywhere in the path
    return full_path:match("https?://") ~= nil
end

function M.get_path()
    local directory = mp.get_property("working-directory")
    -- It seems like in Linux working-directory sometimes returns it without a "/" at the end
    directory = (directory:sub(-1) == '/' or directory:sub(-1) == '\\') and directory or directory .. '/'
    -- For some reason, "path" sometimes returns the absolute path, sometimes it doesn't.
    local file_path = mp.get_property("path")
    local path = utils.join_path(directory, file_path)

    -- Auto-detect ani-cli compatibility by checking for http:// or https:// anywhere in the path
    if path:match("https?://") then
        local media_title = mp.get_property("media-title")
        if media_title and media_title ~= "" then
            return media_title
        end
        return path
    end

    -- Special case for file.mp4
    if path:match("([^/\\]+)$"):lower() == "file.mp4" then
        path = mp.get_property("media-title")
    end

    return path
end

function M.get_python_command()
    local os_name = package.config:sub(1, 1)
    if os_name == '\\' then
        -- Windows
        return "python"
    else
        -- Linux
        return "python3"
    end
end

-- Open the folder that the video is in
function M.open_folder()
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

return M

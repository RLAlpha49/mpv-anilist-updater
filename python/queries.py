"""GraphQL queries for AniList API operations."""


class AniListQueries:
    """GraphQL queries for AniList API operations."""

    # Query to search for anime with optional filters
    # Variables: search (String), year (FuzzyDateInt), page (Int), onList (Boolean)
    SEARCH_ANIME = """
        query($search: String, $year: FuzzyDateInt, $page: Int, $onList: Boolean) {
            Page(page: $page) {
                media (search: $search, type: ANIME, startDate_greater: $year, onList: $onList) {
                    id
                    title { romaji }
                    season
                    seasonYear
                    episodes
                    duration
                    format
                    status
                    mediaListEntry {
                        status
                        progress
                        media {
                            episodes
                        }
                    }
                }
            }
        }
    """

    # Mutation to save/update media list entry (works for both adding and updating)
    # Variables: mediaId (Int), progress (Int), status (MediaListStatus)
    SAVE_MEDIA_LIST_ENTRY = """
        mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
            SaveMediaListEntry (mediaId: $mediaId, progress: $progress, status: $status) {
                status
                id
                progress
                mediaId
            }
        }
    """

"""
A Comprehensive Video Downloader.

Get the User-Input (URL)
Extract relevant information from the URL

if video; download the highest quality video
if audio; download the lowest quality video

convert the resulting file to the desired format

ToDo; max cache time
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Callable, Generator, List
from os import remove
from operator import itemgetter
from itertools import chain

import streamlit as st
import yt_dlp as ytdl
from yt_dlp import DownloadError
from yt_dlp.postprocessor import FFmpegExtractAudioPP, FFmpegVideoConvertorPP

# FFmpegVideoConvertorPP(preferedformat=,), FFmpegExtractAudioPP(preferredcodec=, preferredquality=, nopostoverwrites=False),
from dashboard.util import Config, flatten


EXTENSIONS = {
    "video": ["mp4", "webm"],
    "audio": ["mp3", "m4a", "webm", "wav"],
}


@dataclass
class Settings(Config):
    url_placeholder: str = "https://www.youtube.com/watch?v="
    url_help: str = "URL to Video (Starting with `https`)"
    extension_help: str = "auto ; auto-select best video format"
    speed_feedback: str = "**rate** [mb/s]"
    download_mime: str = "application/octet-stream"
    cache_text: str = "💞 Cache"


class VideoLogger:
    """
    Custom Logging Handler for yt-dlp messages.
    """

    def debug(self, msg):
        """Both Youtube-DL and yt-dlp pass info & debug messages to this method.
        They are distinguished by the `[debug] ` prefix."""
        if msg.startswith("[debug] "):
            # remove debug messages.
            pass
        else:
            self.info(msg)

    def info(self, msg):
        """parse info message."""
        print(msg)

    def warning(self, msg):
        """parse warning message."""
        pass

    def error(self, msg):
        """parse error message."""
        print(msg)


class FormatSelector:

    REGEX_INT = re.compile("\d")
    RESOLUTIONS = ["1080p", "720p", "480p", "360p", "240p", "144p"]
    MERGE = {"mp4": "m4a", "webm": "webm"}
    EXTENSIONS = EXTENSIONS  # create a scoped copy

    def __init__(self, extension: str = "") -> FormatSelector:
        self.extension = ""

    def __repr__(self) -> str:
        if hasattr(self, "download_extension"):
            return f"FormatSelector({self.download_extension})"
        return f"FormatSelector({self.extension})"

    def _get_positive_int(self, value: str) -> int:
        """Get a positive integer from a string."""
        if result := self.REGEX_INT.match(value):
            return int(result.group())
        return 0

    def get_highest_available_quality(self, formats: dict) -> str:
        return max(map(itemgetter("format_note"), formats), key=self._get_positive_int)

    def retrieve_video_format(
        self, formats: dict, quality: str, extension: str = ""
    ) -> dict:
        """Get the best video format for the specified arguments."""
        if not extension:
            extension = self.extension

        return next(
            f
            for f in formats
            if (
                f["vcodec"] != "none"
                and f["acodec"] == "none"
                and (f["ext"] == extension if extension else True)
                and f["format_note"] == quality
            )
        )

    def retrieve_audio_format(self, formats: dict, extension: str = "") -> dict:
        """Get the best audio format for the specified arguments."""
        if not extension:
            extension = self.extension

        return next(
            f
            for f in formats
            if (
                f["vcodec"] == "none"
                and f["acodec"] != "none"
                and (f["ext"] == extension if extension else True)
            )
        )

    def parser(self, ctx) -> Generator[dict]:
        """Get the desired download properties.
        Audio only? max video download to 144p
        Otherwise get highest possible quality, 'till 1080p

        Args:
            ctx (yt.context): The download context (video metadata)

        Returns:
            Dict with the proper download settings.

        Raises:
            ValueError if the requested extension is not available.
        """
        if self.extension and self.extension not in chain.from_iterable(
            self.EXTENSIONS.values()
        ):  # flatten the list and check if the extension is available
            raise ValueError(f"Extension {self.extension} is not available.")

        # Revert to get best->worst
        formats = ctx.get("formats", [])[::-1]
        is_audio = False

        if self.extension in self.EXTENSIONS["audio"]:
            # audio formats will stil require a video request,
            # hence we set the quality to 144p
            quality = "144p"
            is_audio = True
        else:
            if (
                quality := self.get_highest_available_quality(formats)
            ) not in self.RESOLUTIONS:
                # Get the highest available quality <= 1080p
                quality = "1080p"

        # get the desired video quality/format and best audio
        # (in all cases we want the best audio)
        video = self.retrieve_video_format(formats, quality)
        audio = self.retrieve_audio_format(
            formats,
            extension=(self.extension if is_audio else self.MERGE[video["ext"]]),
        )

        yield {
            "format_id": f'{video["format_id"]}+{audio["format_id"]}',
            "ext": f'{video["ext"]}',
            "requested_formats": [video, audio],
            "protocol": f'{video["protocol"]}+{audio["protocol"]}',
        }


class Downloader:
    """
    Construct a Downloader object.

    Available attributes after *successfully* downloading a video:
    - metadata: dict with video metadata
    - location: path to the downloaded video
    - extension: the extension of the video
    - storage: the path to the storage folder
    - url: the url of the video
    - verbose: whether or not to print debug messages
    - banned: list of banned words in the title
    - ydl_opts: dict with ytdl options
    """

    def __init__(
        self,
        url: str,
        extension: str = "",
        storage: str = "./temp",
        verbose: bool = False,
    ) -> Downloader:
        self.url = url
        self.extension = extension
        self.storage = storage

        # Set through local `.config`;
        self.banned = ["porn", "xxx"]
        self.formatselector = FormatSelector(self.extension)

        self.ydl_opts = {
            "format": self.formatselector.parser,
            "outtmpl": f"{self.storage}/%(title)s.%(ext)s",
            "verbose": verbose,
            "logging": VideoLogger(),
            # "ffmpeg_location": "ffmpeg",
            # ToDo; allow --split-chapters
        }

    def __repr__(self) -> str:
        if hasattr(self, "metadata"):
            return f'Downloader({self.metadata["title"]})'
        return f"Downloader({self.url})"

    def __del__(self):
        """remove the temporary video."""
        try:
            remove(self.location)
        except FileNotFoundError:
            print(f"No temporary video to remove for {self}.")
        except AttributeError:
            print(f"Location could not be found for {self}.")

    def _video_filter(self, info, *, incomplete):
        """yt-dlp internal download filter."""
        duration = info.get("duration")
        if duration and duration > 3600:
            return "The selected video is too long."

    @property
    def location(self):
        """video file path for the provided URL."""
        if not hasattr(self, "file_path"):
            raise AttributeError(
                "Can't get location of file before it's been downloaded."
            )
        return self.file_path

    @property
    def content(self):
        if not hasattr(self, "file_path"):
            raise AttributeError("Video has not been downloaded yet.")

        with open(self.file_path, "rb") as video_file:
            return video_file.read()

    def _check_url(self, url: str) -> bool:
        """`sanitize` the url content."""

        return not any(
            (
                url.startswith("https"),
                *[x not in url for x in self.banned],
                "watch" in url,
                # ToDo; update so we can dynamically allow playlists/channels.
                "you" in url,
            )
        )

    def update_ydl_config(
        self,
        ydl_options: Dict[str, Any] | None = None,
        progression: Dict[str, Any] | None = None,
    ):
        """update the yt-dlp options accordingly."""
        if ydl_options is not None:
            self.ydl_opts.update(ydl_options)
        if progression is not None:
            self.ydl_opts.update(progression)

        return self

    def download_video(
        self, url: str, processors: List[Callable] | None = None
    ) -> None:
        """download a video using yt_dlp.

        Args:
            url (str): the url of the video to download.

        Returns:
            Self

        Raises:
            ValueError if the url is not valid.
            DownloadError if the video could not be downloaded.
        """
        if self._check_url(url):
            raise ValueError("Recieved an invalid URL, stopping...")

        # Download the requested video
        with ytdl.YoutubeDL(self.ydl_opts) as video_downloader:
            self.metadata = video_downloader.extract_info(
                url,
                download=False,
                # `process=False` to avoid additional downloading
                process=False,
            )

            if processors is not None and processors:
                [  # Check if we do not get an empty list.
                    video_downloader.add_post_processor(processor)
                    for processor in processors
                ]

            error_code = video_downloader.download([url])

            if error_code == 1:
                raise DownloadError("Video download failed.")

            self.file_path = f"{self.storage}/{self.metadata['title']}.{self.extension}"

        return self


class Video:
    """
    Display the Video Downloader page using Streamlit.
    """

    # We only care about the available formats, not the grouped ones.
    EXTENSIONS = EXTENSIONS

    def __init__(self, config) -> Video:
        self.config = config  # Provide customizations to the video downloader.
        # Allow for item caching as the video is downloaded.
        self.cache = {"delta": 0, "update_hook": False, "download_progress": 0}

    def _setup_input_form(self) -> bool:
        """Create a generic input form."""
        with st.form("How can I help?"):
            self.video_url = st.text_input(
                "URL:",
                value="",
                placeholder=self.config["url_placeholder"],
                help=self.config["url_help"],
                key="video_url",
            )

            self.extension = st.selectbox(
                "Extension (mp3 | m4a = audio)",
                ["auto"] + list(set(flatten(EXTENSIONS.values()))),
                help=self.config["extension_help"],
            )

            start_download = st.form_submit_button("Start Download")

        return start_download

    def _display_progression(self, info: Dict[str, Any]) -> None:
        """Display Download Progression."""
        download_progression = int(
            (info["downloaded_bytes"] / info["total_bytes"]) * 100
        )

        if (
            download_progression <= self.cache["download_progress"]
            or info.get("status") == "finished"
        ):
            self.cache["update_hook"] = True
            return

        self.cache["download_progress"] = download_progression

        self.progression_bar.progress(
            download_progression
        )  # Optionally, simply display some text.

        # Somehow we still need to include a 'is not None' clause outside `.get`
        speed = info.get("speed", 0) if info.get("speed", 0) is not None else 0
        speed_rate = int(speed) // 1e6
        new_delta = speed_rate - self.cache["delta"]

        if -1 < new_delta > 1:
            self.holder.empty()
            self.holder.markdown(f"{self.config['speed_feedback']} | {speed_rate}")
            self.cache["delta"] = speed_rate

    def _create_download_button(self, content: bytes, title: str) -> None:
        """Create a Download button for a video+audio file."""
        st.download_button(
            label=f"Download {title}!",
            data=content,
            file_name=title,
            mime=self.config["download_mime"],
        )

    def write(self, title: str = "Video Downloader") -> None:
        st.title(title)
        start_download = self._setup_input_form()

        # Ensure we have some placeholders for our content.
        # We use empty so we can clear the section after n-seconds.
        self.notification_placeholder = st.empty()

        # When the button has been pressed.
        if not start_download:
            st.stop()

        # Button is pressed while all is empty.
        if self.video_url == "":
            st.stop()

        # Set the progression bar.
        progress_col, self.rate = st.columns([8, 2])
        with progress_col:
            self.progression_bar = st.progress(0)

        with self.rate:
            self.holder = st.empty()

            if self.extension == "auto":
                self.extension = ""

            video_downloader = Downloader(self.video_url, self.extension)

            post_processors = []
            if self.extension in self.EXTENSIONS["audio"]:
                post_processors.append(
                    FFmpegExtractAudioPP(preferredcodec=self.extension)
                )
            if self.extension in self.EXTENSIONS["video"]:
                post_processors.append(
                    FFmpegVideoConvertorPP(preferedformat=self.extension)
                )

            try:
                # Update the options and start downloading.
                video = video_downloader.update_ydl_config(
                    progression={
                        "progress_hooks": [
                            self._display_progression,
                        ]
                    }
                ).download_video(self.video_url, post_processors)

            except DownloadError:
                self.notification_placeholder.error(
                    "The format is not available for this video."
                )
                st.stop()

        if isinstance(video, str):
            self._error(self.notification_placeholder, video)
            st.stop()

        elif video.content is None:
            self._error(
                self.notification_placeholder,
                "Video Download came back empty, please try again.",
            )

        if not self.cache["update_hook"]:
            self.rate.text(self.config["cache_text"])
            self.progression_bar.progress(100)

        col1, col2 = st.columns([1, 3])
        with col1:
            self.data = video.content
            self._create_download_button(self.data, video.metadata["title"])
        with col2:
            if video.metadata.get("thumbnail") is not None:
                st.image(
                    video.metadata["thumbnail"],
                    # width=300,
                )

        # ToDo; Show metadata
        # json_formatted_str = json.dumps(obj, indent=4)
        # st.write(json_formatted_str)
        # OR st.json()!


Video(Settings()).write()  # dotenv config

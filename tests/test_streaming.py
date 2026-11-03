import pytest

from behavioralsignals import StreamingOptions
from behavioralsignals.base import BaseClient
from behavioralsignals.deepfakes import Deepfakes
from behavioralsignals.generated import api_pb2 as pb
from behavioralsignals.behavioral import Behavioral
from behavioralsignals.configuration import Configuration


RPC_PATH = "/behavioral_api.grpc.v1.BehavioralStreamingApi/"


class FakeChannel:
    """Stands in for a gRPC channel: records the call and replays canned responses."""

    def __init__(self, responses):
        self.responses = responses
        self.path = None
        self.sent = []

    def stream_stream(self, path, **kwargs):
        def call(messages):
            self.path = path
            self.sent.extend(messages)
            return iter(self.responses)

        return call

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def fake_channel(monkeypatch, responses=()):
    """Replaces the gRPC channel. Returns the channel that recorded the call."""
    channel = FakeChannel(responses)
    monkeypatch.setattr(BaseClient, "_get_channel_context", lambda self: channel)
    return channel


def make_client(cls):
    """Client without network: only the configuration the streaming call needs."""
    client = cls.__new__(cls)
    client.config = Configuration(cid="123", api_key="secret")
    return client


def stream_audio(cls, level="utterance", audio=(b"aa", b"bb")):
    options = StreamingOptions(encoding="LINEAR_PCM", sample_rate=8000, level=level)
    return list(make_client(cls).stream_audio(audio_stream=iter(audio), options=options))


@pytest.mark.parametrize(
    ("cls", "rpc"), [(Behavioral, "StreamAudio"), (Deepfakes, "DeepfakeDetection")]
)
def test_stream_audio_calls_its_own_rpc(monkeypatch, cls, rpc):
    channel = fake_channel(monkeypatch)
    stream_audio(cls)
    assert channel.path == RPC_PATH + rpc


@pytest.mark.parametrize("cls", [Behavioral, Deepfakes])
def test_stream_audio_sends_the_config_first_then_the_chunks(monkeypatch, cls):
    channel = fake_channel(monkeypatch)
    stream_audio(cls)
    config, *chunks = channel.sent
    assert config.config.sample_rate_hertz == 8000
    assert config.config.encoding == pb.AudioEncoding.LINEAR_PCM
    assert config.config.level == pb.Level.utterance
    assert config.audio_content == b""
    assert [message.audio_content for message in chunks] == [b"aa", b"bb"]


def test_stream_audio_sends_the_credentials_on_every_message(monkeypatch):
    channel = fake_channel(monkeypatch)
    stream_audio(Behavioral)
    assert {(message.cid, message.x_auth_token) for message in channel.sent} == {(123, "secret")}


def test_streaming_level_all_asks_for_both_levels(monkeypatch):
    channel = fake_channel(monkeypatch)
    stream_audio(Behavioral, level="all")
    assert not channel.sent[0].config.HasField("level")


def test_streaming_sends_focus_only_when_asked():
    assert not StreamingOptions(encoding="LINEAR_PCM").to_pb_config().HasField("focus")
    config = StreamingOptions(
        encoding="LINEAR_PCM", focus=["angry", "low_confidence"], sensitivity="high"
    ).to_pb_config()
    assert list(config.focus.labels) == ["angry", "low_confidence"]
    assert config.focus.sensitivity == "high"


def test_streaming_sends_an_empty_focus_list_for_the_api_to_reject():
    config = StreamingOptions(encoding="LINEAR_PCM", focus=[]).to_pb_config()
    assert config.HasField("focus") and list(config.focus.labels) == []


@pytest.mark.parametrize("cls", [Behavioral, Deepfakes])
def test_stream_audio_parses_the_responses(monkeypatch, cls):
    response = pb.StreamResult(
        cid=123,
        pid=7,
        message_id=2,
        result=[
            pb.InferenceResult(
                id="1",
                start_time="0.487",
                end_time="3.001",
                task="emotion",
                final_label="sad",
                prediction=[pb.Prediction(label="sad", posterior="0.9")],
            )
        ],
    )
    fake_channel(monkeypatch, [response])
    results = stream_audio(cls)
    assert [(result.pid, result.message_id) for result in results] == [(7, 2)]
    item = results[0].results[0]
    assert (item.st, item.et, item.task, item.finalLabel) == (0.487, 3.001, "emotion", "sad")
    assert [(p.label, p.posterior) for p in item.prediction] == [("sad", "0.9")]


def test_stream_audio_parses_grouped_outputs(monkeypatch):
    score = pb.GroupedOutput(prediction=[pb.Prediction(score="0.81")])
    response = pb.StreamResult(
        pid=7,
        result=[
            pb.InferenceResult(id="1", task="signal_quality", outputs={"snr": score}),
            pb.InferenceResult(id="1", task="emotion", final_label="sad"),
        ],
    )
    fake_channel(monkeypatch, [response])
    quality, emotion = stream_audio(Behavioral)[0].results
    assert quality.outputs["snr"].prediction[0].score == "0.81"
    assert emotion.outputs is None


def test_stream_audio_drops_the_empty_fields_of_a_score(monkeypatch):
    response = pb.StreamResult(
        pid=7,
        result=[
            pb.InferenceResult(
                id="2",
                start_time="0.00",
                end_time="2.00",
                task="intensity",
                level=pb.Level.Value("segment"),
                prediction=[pb.Prediction(score="0.3231", posterior="")],
            )
        ],
    )
    fake_channel(monkeypatch, [response])
    item = stream_audio(Behavioral)[0].results[0]
    assert item.model_dump(exclude={"st", "et"}) == {
        "id": "2",
        "startTime": "0.00",
        "endTime": "2.00",
        "task": "intensity",
        "prediction": [{"score": "0.3231"}],
        "level": "segment",
    }

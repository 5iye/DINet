
import numpy as np
import warnings
import resampy
from scipy.io import wavfile
from python_speech_features import mfcc
import tensorflow as tf


class DeepSpeech():

    def __init__(self, model_path):
        self.model = tf.lite.Interpreter(model_path)
        self.model.allocate_tensors()
        self.target_sample_rate = 16000
        self.input_details = self.model.get_input_details()
        self.output_details = self.model.get_output_details()

    def conv_audio_to_deepspeech_input_vector(self,
                                              audio,
                                              sample_rate,
                                              num_cepstrum,
                                              num_context):
        # Get mfcc coefficients:
        features = mfcc(
            signal=audio,
            samplerate=sample_rate,
            numcep=num_cepstrum)

        # We only keep every second feature (BiRNN stride = 2):
        features = features[::2]

        # One stride per time step in the input:
        num_strides = len(features)

        # Add empty initial and final contexts:
        empty_context = np.zeros((num_context, num_cepstrum), dtype=features.dtype)
        features = np.concatenate((empty_context, features, empty_context))

        # Create a view into the array with overlapping strides of size
        # numcontext (past) + 1 (present) + numcontext (future):
        window_size = 2 * num_context + 1
        train_inputs = np.lib.stride_tricks.as_strided(
            features,
            shape=(num_strides, window_size, num_cepstrum),
            strides=(features.strides[0],
                     features.strides[0], features.strides[1]),
            writeable=False)

        # Flatten the second and third dimensions:
        train_inputs = np.reshape(train_inputs, [num_strides, -1])

        train_inputs = np.copy(train_inputs)
        train_inputs = (train_inputs - np.mean(train_inputs)) / \
                       np.std(train_inputs)

        return train_inputs

    def compute_audio_feature(self,audio_path):
        audio_sample_rate, audio = wavfile.read(audio_path)
        if audio.ndim != 1:
            warnings.warn(
                "Audio has multiple channels, the first channel is used")
            audio = audio[:, 0]
        if audio_sample_rate != self.target_sample_rate:
            resampled_audio = resampy.resample(
                x=audio.astype(np.float),
                sr_orig=audio_sample_rate,
                sr_new=self.target_sample_rate)
        else:
            resampled_audio = audio.astype(np.float)

        input_vector = self.conv_audio_to_deepspeech_input_vector(audio=resampled_audio.astype(np.int16), sample_rate=self.target_sample_rate, num_cepstrum=26, num_context=9)
        input_vector = input_vector.astype(np.float32)

        # TensorFlow Lite 모델에 입력 설정
        self.model.set_tensor(self.input_details[0]['index'], [input_vector])
        self.model.invoke()

        # 결과 가져오기
        ds_features = self.model.get_tensor(self.output_details[0]['index'])
        return ds_features


if __name__ == '__main__':
    audio_path = r'./00168.wav'
    model_path = r'./output_graph.pb'
    DSModel = DeepSpeech(model_path)
    ds_feature = DSModel.compute_audio_feature(audio_path)
    print(ds_feature)


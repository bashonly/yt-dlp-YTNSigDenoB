import os
import tempfile
import contextlib
import subprocess

from yt_dlp.utils import (
    ExtractorError,
    check_executable,
    shell_quote,
    Popen,
)
from yt_dlp.extractor.youtube import YoutubeIE


class Youtube_NsigDenoIE(YoutubeIE, plugin_name='NSigDeno'):
    _TEMP_FILES = []
    DENO_INSTALL_HINT = 'Please download it from https://deno.land/'

    def __del__(self):
        for name in self._TEMP_FILES:
            with contextlib.suppress(OSError, KeyError):
                os.remove(name)

    def _extract_n_function_from_code(self, jsi, func_code):
        args, func_body = func_code
        func = jsi.extract_function_from_code(*func_code)

        def extract_nsig(s):
            if not self._configuration_arg('bypass_native_jsi'):
                try:
                    ret = func([s])
                except Exception:
                    ret = None
                if ret and not ret.startswith('enhanced_except_'):
                    return ret
                self.report_warning('Native JSInterpreter failed to decrypt, trying with Deno')
                ret = None

            exe = check_executable('deno', ['--version'])
            if not exe:
                self.report_warning(f'Deno not found, {self.DENO_INSTALL_HINT}')
                raise ExtractorError(f'Deno not found, {self.DENO_INSTALL_HINT}', expected=True)

            tmp = tempfile.NamedTemporaryFile(delete=False)
            tmp.close()
            self._TEMP_FILES.append(tmp.name)

            jscode = f'console.log(function({", ".join(args)}) {{ {func_body} }}({s!r}));'
            with open(tmp.name, 'w', encoding='utf-8') as f:
                f.write(jscode)

            if not self._configuration_arg('deno_no_jitless'):
                cmd = [exe, 'run', '--v8-flags=--jitless', tmp.name]
            else:
                cmd = [exe, 'run', tmp.name]
            self.write_debug(f'Deno command line: {shell_quote(cmd)}')

            try:
                stdout, stderr, returncode = Popen.run(cmd, timeout=10,
                                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                raise ExtractorError('Executing JS failed: Unable to run Deno binary', cause=e)
            if returncode:
                raise ExtractorError(f'Executing JS failed with returncode {returncode}:\n{stderr.strip()}')

            ret = stdout.strip()

            if ret.startswith('enhanced_except_'):
                raise Exception('Signature function returned an exception')

            return ret

        return extract_nsig


__all__ = []

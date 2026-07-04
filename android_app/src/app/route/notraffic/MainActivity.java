package app.route.notraffic;

import android.Manifest;
import android.app.Activity;
import android.app.PictureInPictureParams;
import android.content.Context;
import android.content.Intent;
import android.content.ComponentName;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.provider.Settings;
import android.service.notification.NotificationListenerService;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Rational;
import android.view.WindowManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.util.Locale;

/**
 * WebView shell around assets/index.html (OSM + OSRM navigation).
 * Native extras:
 *   - Greek text-to-speech bridge (window.AndroidTTS)
 *   - audio ducking: lowers background music while speaking (like Maps)
 *   - Picture-in-Picture: a small floating map window when you leave the app
 */
public class MainActivity extends Activity {

    private WebView web;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;
    private TextToSpeech tts;
    private boolean ttsGreekReady = false;
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusReq;   // API 26+
    private volatile boolean navigating = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Navigation app: keep the screen on while in the foreground.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);

        // Native Greek TTS engine.
        tts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status != TextToSpeech.SUCCESS) return;
                int r = tts.setLanguage(new Locale("el", "GR"));
                if (r == TextToSpeech.LANG_MISSING_DATA
                        || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                    ttsGreekReady = false;
                    try {
                        startActivity(new Intent(
                                TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
                    } catch (Exception ignored) { }
                } else {
                    ttsGreekReady = true;
                }
                // Mark speech as navigation guidance (helps the system duck music).
                tts.setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build());
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String id) { }
                    @Override public void onDone(String id) { duckMusic(false); }
                    @Override public void onError(String id) { duckMusic(false); }
                });
            }
        });

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setGeolocationEnabled(true);
        // The page is loaded from file:///android_asset/, whose origin would
        // normally block fetch() calls to the geocoding/routing servers.
        s.setAllowUniversalAccessFromFileURLs(true);

        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(
                    String origin, GeolocationPermissions.Callback callback) {
                if (hasLocationPermission()) {
                    callback.invoke(origin, true, false);
                } else if (Build.VERSION.SDK_INT >= 23) {
                    pendingGeoCallback = callback;
                    pendingGeoOrigin = origin;
                    requestPermissions(new String[] {
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION }, 1);
                } else {
                    callback.invoke(origin, false, false);
                }
            }
        });

        web.addJavascriptInterface(new TtsBridge(), "AndroidTTS");
        web.addJavascriptInterface(new AppBridge(), "AndroidApp");
        web.addJavascriptInterface(new AlertsBridge(), "AndroidAlerts");
        web.loadUrl("file:///android_asset/index.html");

        setContentView(web);
    }

    /** JavaScript bridge: window.AndroidTTS.speak("…"). */
    private class TtsBridge {
        @JavascriptInterface
        public void speak(String text) {
            if (tts == null || !ttsGreekReady || text == null) return;
            duckMusic(true);   // lower background music, then speak
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "nav");
        }

        @JavascriptInterface
        public boolean available() {
            return ttsGreekReady;
        }
    }

    /** JavaScript bridge: window.AndroidApp.* (nav state / PiP support). */
    private class AppBridge {
        @JavascriptInterface
        public void setNavigating(boolean on) {
            navigating = on;
        }

        @JavascriptInterface
        public boolean pipSupported() {
            return Build.VERSION.SDK_INT >= 26 && getPackageManager()
                    .hasSystemFeature(PackageManager.FEATURE_PICTURE_IN_PICTURE);
        }
    }

    /** JavaScript bridge: window.AndroidAlerts.* (Viber group alerts). */
    private class AlertsBridge {
        @JavascriptInterface
        public String list() {
            return getSharedPreferences(AlertListener.PREFS, MODE_PRIVATE)
                    .getString(AlertListener.KEY_ITEMS, "[]");
        }

        @JavascriptInterface
        public void setGroups(String pipeSeparated) {
            getSharedPreferences(AlertListener.PREFS, MODE_PRIVATE).edit()
                    .putString(AlertListener.KEY_GROUPS,
                            pipeSeparated == null ? "" : pipeSeparated).apply();
        }

        @JavascriptInterface
        public boolean hasAccess() {
            String enabled = Settings.Secure.getString(getContentResolver(),
                    "enabled_notification_listeners");
            return enabled != null && enabled.contains(getPackageName());
        }

        @JavascriptInterface
        public void openAccessSettings() {
            try {
                startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception e) {
                try { startActivity(new Intent(Settings.ACTION_SETTINGS)); }
                catch (Exception ignored) { }
            }
        }

        // ---- Accessibility reader (reads the open chat from the screen) ----
        @JavascriptInterface
        public boolean hasReader() {
            String enabled = Settings.Secure.getString(getContentResolver(),
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            return enabled != null && enabled.contains(getPackageName());
        }

        @JavascriptInterface
        public void openReaderSettings() {
            try {
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception e) {
                try { startActivity(new Intent(Settings.ACTION_SETTINGS)); }
                catch (Exception ignored) { }
            }
        }

        @JavascriptInterface
        public void clear() {
            getSharedPreferences(AlertListener.PREFS, MODE_PRIVATE).edit()
                    .putString(AlertListener.KEY_ITEMS, "[]").apply();
        }
    }

    // ---- Audio ducking: lower other apps' music while the guidance speaks ----
    private void duckMusic(boolean duck) {
        if (audioManager == null) return;
        try {
            if (Build.VERSION.SDK_INT >= 26) {
                if (duck) {
                    audioFocusReq = new AudioFocusRequest.Builder(
                            AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                            .setAudioAttributes(new AudioAttributes.Builder()
                                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                    .build())
                            .build();
                    audioManager.requestAudioFocus(audioFocusReq);
                } else if (audioFocusReq != null) {
                    audioManager.abandonAudioFocusRequest(audioFocusReq);
                    audioFocusReq = null;
                }
            } else {
                if (duck) {
                    audioManager.requestAudioFocus(null, AudioManager.STREAM_MUSIC,
                            AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK);
                } else {
                    audioManager.abandonAudioFocus(null);
                }
            }
        } catch (Exception ignored) { }
    }

    // ---- Picture-in-Picture: shrink to a floating window when leaving ----
    @Override
    public void onUserLeaveHint() {
        super.onUserLeaveHint();
        if (navigating && Build.VERSION.SDK_INT >= 26 && getPackageManager()
                .hasSystemFeature(PackageManager.FEATURE_PICTURE_IN_PICTURE)) {
            try {
                enterPictureInPictureMode(new PictureInPictureParams.Builder()
                        .setAspectRatio(new Rational(3, 4)).build());
            } catch (Exception ignored) { }
        }
    }

    @Override
    public void onPictureInPictureModeChanged(boolean isInPip, Configuration newConfig) {
        super.onPictureInPictureModeChanged(isInPip, newConfig);
        if (web != null) {
            // Let the page switch to a compact layout while floating.
            web.evaluateJavascript("document.body.classList."
                    + (isInPip ? "add" : "remove") + "('pip')", null);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // After the user grants Notification access, some devices don't bind
        // the listener until a rebind is requested — ask for one every time
        // the app comes to the foreground.
        if (Build.VERSION.SDK_INT >= 24) {
            try {
                NotificationListenerService.requestRebind(
                        new ComponentName(this, AlertListener.class));
            } catch (Exception ignored) { }
        }
    }

    private boolean hasLocationPermission() {
        return Build.VERSION.SDK_INT < 23
                || checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                        == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
                        == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == 1 && pendingGeoCallback != null) {
            pendingGeoCallback.invoke(pendingGeoOrigin, hasLocationPermission(), false);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        duckMusic(false);
        if (tts != null) {
            tts.stop();
            tts.shutdown();
            tts = null;
        }
        super.onDestroy();
    }
}

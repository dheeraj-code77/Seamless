package com.seamless.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONException;
import org.json.JSONObject;

import androidx.annotation.Nullable;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {
    private WebView webView;
    private TextView statusStrip;
    private ValueCallback<Uri[]> uploadMessage;
    private static final int FILE_CHOOSER_RESULT_CODE = 1001;
    private static final int CAMERA_PERMISSION_REQUEST_CODE = 2001;
    private static final int MAX_CLIPBOARD_CHARS = 65536;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout appLayout = new LinearLayout(this);
        appLayout.setOrientation(LinearLayout.VERTICAL);
        appLayout.setBackgroundColor(Color.parseColor("#ECE7DD"));

        // A slim strip for pairing progress and errors. It stays hidden until
        // there is something worth showing, so the app fills the screen.
        statusStrip = new TextView(this);
        statusStrip.setTextColor(Color.parseColor("#1A231C"));
        statusStrip.setTextSize(13);
        statusStrip.setPadding(dp(16), dp(10), dp(16), dp(10));
        statusStrip.setBackgroundColor(Color.parseColor("#FAF8F3"));
        statusStrip.setVisibility(View.GONE);
        appLayout.addView(statusStrip, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        webView = new WebView(this);
        appLayout.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(appLayout);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setDatabaseEnabled(true);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void pairingCompleted(String deviceName) {
                mainHandler.post(() -> showStatus("Paired with " + deviceName + "."));
            }

            @android.webkit.JavascriptInterface
            public void startQrScan() {
                mainHandler.post(MainActivity.this::requestScan);
            }

            @android.webkit.JavascriptInterface
            public String getClipboard() {
                return readClipboardText();
            }

            @android.webkit.JavascriptInterface
            public void setClipboard(String text) {
                mainHandler.post(() -> writeClipboardText(text));
            }
        }, "SeamlessAndroid");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback,
                                             FileChooserParams fileChooserParams) {
                if (uploadMessage != null) {
                    uploadMessage.onReceiveValue(null);
                }
                uploadMessage = filePathCallback;

                Intent intent = fileChooserParams.createIntent();
                try {
                    startActivityForResult(intent, FILE_CHOOSER_RESULT_CODE);
                } catch (Exception e) {
                    uploadMessage = null;
                    return false;
                }
                return true;
            }
        });

        // Load bundled Seamless mobile interface or local hotspot server
        webView.loadUrl("file:///android_asset/index.html");
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    /** Shows a short message above the app, or hides the strip when given null. */
    private void showStatus(String message) {
        if (message == null || message.trim().isEmpty()) {
            statusStrip.setVisibility(View.GONE);
            return;
        }
        statusStrip.setText(message);
        statusStrip.setVisibility(View.VISIBLE);
    }

    // Camera permission and the QR scanner

    private void requestScan() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            showStatus("Camera access is needed to scan the pairing QR code.");
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST_CODE);
            return;
        }
        launchScanner();
    }

    private void launchScanner() {
        try {
            new IntentIntegrator(this)
                    .setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
                    .setPrompt("Scan the QR code shown in the Windows Seamless app")
                    .setBeepEnabled(false)
                    .setOrientationLocked(true)
                    .initiateScan();
        } catch (Exception e) {
            showStatus("Could not open the camera scanner. Check camera permission and try again.");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != CAMERA_PERMISSION_REQUEST_CODE) {
            return;
        }
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            showStatus("");
            launchScanner();
        } else {
            showCameraDeniedMessage();
        }
    }

    private void showCameraDeniedMessage() {
        new AlertDialog.Builder(this)
                .setTitle("Camera access needed")
                .setMessage("Seamless uses the camera only to read the pairing QR code on your laptop. "
                        + "Allow camera access to scan it, or enter the pairing PIN manually instead.")
                .setPositiveButton("Try again", (dialog, which) -> requestScan())
                .setNegativeButton("Enter PIN instead", (dialog, which) -> {
                    showStatus("");
                    webView.evaluateJavascript("openMobilePairingModal()", null);
                })
                .show();
    }

    // Clipboard access

    private String readClipboardText() {
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard == null || !clipboard.hasPrimaryClip()) {
                return "";
            }
            ClipData clip = clipboard.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) {
                return "";
            }
            CharSequence text = clip.getItemAt(0).getText();
            if (text == null || text.length() > MAX_CLIPBOARD_CHARS) {
                return "";
            }
            return text.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private void writeClipboardText(String text) {
        if (text == null || text.isEmpty() || text.length() > MAX_CLIPBOARD_CHARS) {
            return;
        }
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("Seamless clipboard", text));
            }
        } catch (Exception e) {
            // Nothing to do here; the next sync attempt tries again.
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        IntentResult scanResult = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (scanResult != null) {
            if (scanResult.getContents() == null) {
                showStatus("QR scan cancelled. Your existing connection is unchanged.");
            } else {
                connectToScannedLaptop(scanResult.getContents());
            }
        } else if (requestCode == FILE_CHOOSER_RESULT_CODE) {
            if (uploadMessage != null) {
                Uri[] results = null;
                if (resultCode == Activity.RESULT_OK && data != null) {
                    String dataString = data.getDataString();
                    if (dataString != null) {
                        results = new Uri[]{Uri.parse(dataString)};
                    } else if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    }
                }
                uploadMessage.onReceiveValue(results);
                uploadMessage = null;
            }
        }
    }

    private void connectToScannedLaptop(String contents) {
        final JSONObject qr;
        final String host;
        final String deviceId;
        final String pairingToken;
        final int port;
        try {
            qr = new JSONObject(contents);
            if (!"seamless".equals(qr.optString("app")) || qr.optInt("version") != 1) {
                throw new JSONException("This QR code is not a supported Seamless pairing code.");
            }
            host = qr.getString("host");
            deviceId = qr.getString("device_id");
            pairingToken = qr.optString("pairing_token", "");
            port = qr.getInt("port");
            if (!isPrivateIpv4(host) || port < 1 || port > 65535 || deviceId.isEmpty()) {
                throw new JSONException("The QR code does not contain a valid local laptop address.");
            }
        } catch (JSONException e) {
            showStatus(e.getMessage() == null
                    ? "Invalid Seamless QR code. Try scanning the code shown on the laptop."
                    : e.getMessage());
            return;
        }

        showStatus("Checking " + host + ":" + port + " on your local network…");
        new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                URL url = new URL("http://" + host + ":" + port + "/api/device/info");
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(4000);
                connection.setReadTimeout(4000);
                connection.setRequestMethod("GET");
                if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) {
                    throw new IllegalStateException("The laptop did not accept the connection.");
                }
                StringBuilder response = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(connection.getInputStream(), "UTF-8"))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        response.append(line);
                    }
                }
                JSONObject info = new JSONObject(response.toString());
                if (!"windows".equals(info.optString("device_type"))
                        || !deviceId.equals(info.optString("device_id"))) {
                    throw new IllegalStateException(
                            "The laptop identity did not match this QR code. Scan a current code from Seamless.");
                }
                mainHandler.post(() -> {
                    showStatus("Connected to " + info.optString("device_name")
                            + ". Pairing you now…");
                    String hostArgument = JSONObject.quote(host);
                    String tokenArgument = JSONObject.quote(pairingToken);
                    webView.evaluateJavascript(
                            "setLaptopAddress(" + hostArgument + "," + port + "," + tokenArgument + ")", null);
                });
            } catch (Exception e) {
                String message = e instanceof java.net.SocketTimeoutException
                        ? "Connection timed out. Put both devices on the same Wi-Fi and check Seamless is running."
                        : "Could not connect to that laptop. Check the same Wi-Fi network and scan its current QR code.";
                mainHandler.post(() -> showStatus(message));
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
        }).start();
    }

    private boolean isPrivateIpv4(String host) {
        if (!host.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) {
            return false;
        }
        String[] parts = host.split("\\.");
        int[] octets = new int[4];
        for (int i = 0; i < parts.length; i++) {
            octets[i] = Integer.parseInt(parts[i]);
            if (octets[i] > 255 || !Integer.toString(octets[i]).equals(parts[i])) {
                return false;
            }
        }
        return octets[0] == 10
                || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
                || (octets[0] == 192 && octets[1] == 168)
                || (octets[0] == 169 && octets[1] == 254);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}

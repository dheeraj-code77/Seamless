package com.seamless.app;

import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
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
    private TextView pairingStatus;
    private ValueCallback<Uri[]> uploadMessage;
    private static final int FILE_CHOOSER_RESULT_CODE = 1001;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout appLayout = new LinearLayout(this);
        appLayout.setOrientation(LinearLayout.VERTICAL);
        appLayout.setBackgroundColor(Color.parseColor("#ECE7DD"));

        TextView heading = new TextView(this);
        heading.setText("Connect to Windows");
        heading.setTextColor(Color.parseColor("#1A231C"));
        heading.setTextSize(18);
        heading.setPadding(dp(16), dp(12), dp(16), dp(2));
        appLayout.addView(heading);

        pairingStatus = new TextView(this);
        pairingStatus.setText("Scan the QR code shown in the Windows Seamless app.");
        pairingStatus.setTextColor(Color.parseColor("#687469"));
        pairingStatus.setTextSize(13);
        pairingStatus.setPadding(dp(16), dp(2), dp(16), dp(8));
        appLayout.addView(pairingStatus);

        Button scanButton = new Button(this);
        scanButton.setText("Scan QR Code");
        scanButton.setTextColor(Color.WHITE);
        scanButton.setBackgroundTintList(ColorStateList.valueOf(Color.parseColor("#456F5B")));
        scanButton.setOnClickListener(view -> startQrScan());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        buttonParams.setMargins(dp(16), 0, dp(16), dp(8));
        appLayout.addView(scanButton, buttonParams);

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
                mainHandler.post(() -> pairingStatus.setText("Paired with " + deviceName + "."));
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

    private void startQrScan() {
        try {
            new IntentIntegrator(this)
                    .setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
                    .setPrompt("Scan the QR code shown in the Windows Seamless app")
                    .setBeepEnabled(false)
                    .setOrientationLocked(false)
                    .initiateScan();
        } catch (Exception e) {
            pairingStatus.setText("Could not open the camera scanner. Check camera permission and try again.");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        IntentResult scanResult = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (scanResult != null) {
            if (scanResult.getContents() == null) {
                pairingStatus.setText("QR scan cancelled. Your existing connection is unchanged.");
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
            pairingStatus.setText(e.getMessage() == null
                    ? "Invalid Seamless QR code. Try scanning the code shown on the laptop."
                    : e.getMessage());
            return;
        }

        pairingStatus.setText("Checking " + host + ":" + port + " on your local network…");
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
                    pairingStatus.setText("Connected to " + info.optString("device_name")
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
                mainHandler.post(() -> pairingStatus.setText(message));
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

package br.com.siopa.offline;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.View;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;
import java.io.File;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/** The web application is bundled from app/static at build time; no remote UI is loaded. */
public final class MainActivity extends Activity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final String HOME = ORIGIN + "/assets/siopa/index.html";
    private static final int PICK_PHOTO = 10, EXPORT = 11, CAMERA_PERMISSION = 12, LOCATION_PERMISSION = 13;
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private Uri cameraUri;
    private File cameraFile;
    private GeolocationPermissions.Callback locationCallback;
    private String locationOrigin;
    private String pendingExport;

    // JS is required by the bundled measurement UI; remote pages cannot navigate
    // inside this WebView and user-controlled labels are rendered as text.
    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        webView = new WebView(this);
        webView.setBackgroundColor(0xfff1eadf);
        setContentView(webView);
        // Android 15 enables edge-to-edge; keep controls clear of system bars.
        webView.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        webView.setFitsSystemWindows(true);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setGeolocationEnabled(true);
        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        webView.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (isLocal(request.getUrl().toString())) return false;
                if (request.isForMainFrame() && "https".equals(request.getUrl().getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); } catch (Exception ignored) { toast("Nenhum navegador disponível."); }
                }
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                finishFile(null);
                fileCallback = callback;
                if (params.isCaptureEnabled()) {
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchCamera();
                    else requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
                } else {
                    Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);
                    try { startActivityForResult(intent, PICK_PHOTO); } catch (Exception error) { finishFile(null); toast("Nenhum seletor de imagens disponível."); }
                }
                return true;
            }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                if (!ORIGIN.equals(origin) && !(ORIGIN + "/").equals(origin)) { callback.invoke(origin, false, false); return; }
                if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) callback.invoke(origin, true, false);
                else { locationCallback = callback; locationOrigin = origin; requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, LOCATION_PERMISSION); }
            }
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
        });
        webView.addJavascriptInterface(new ExportBridge(), "SiopaAndroid");
        if (savedState == null || webView.restoreState(savedState) == null) webView.loadUrl(HOME);
    }
    private boolean isLocal(String url) { return url != null && url.startsWith(ORIGIN + "/assets/siopa/"); }
    private void launchCamera() {
        try {
            File directory = new File(getCacheDir(), "camera");
            if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Cache indisponível");
            cameraFile = File.createTempFile("amostra-", ".jpg", directory);
            cameraUri = FileProvider.getUriForFile(this, getPackageName() + ".files", cameraFile);
            Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            intent.putExtra(MediaStore.EXTRA_OUTPUT, cameraUri);
            intent.setClipData(ClipData.newRawUri("foto", cameraUri));
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivityForResult(intent, PICK_PHOTO);
        } catch (Exception error) { cameraUri = null; finishFile(null); toast("Não foi possível abrir a câmera. Use escolher foto."); }
    }
    private void finishFile(Uri[] result) { if (fileCallback != null) { fileCallback.onReceiveValue(result); fileCallback = null; } }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        boolean granted = false; for (int result : results) granted |= result == PackageManager.PERMISSION_GRANTED;
        if (code == CAMERA_PERMISSION) { if (granted) launchCamera(); else { finishFile(null); toast("Câmera não autorizada. Você pode escolher uma foto existente."); } }
        if (code == LOCATION_PERMISSION && locationCallback != null) { locationCallback.invoke(locationOrigin, granted, false); locationCallback = null; }
    }
    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code == PICK_PHOTO) {
            if (result != RESULT_OK) { finishFile(null); if (cameraFile != null) cameraFile.delete(); }
            else if (cameraUri != null) finishFile(new Uri[]{cameraUri});
            else finishFile(data != null && data.getData() != null ? new Uri[]{data.getData()} : null);
            cameraUri = null;
        }
        if (code == EXPORT) {
            String contents = pendingExport; pendingExport = null;
            if (result == RESULT_OK && data != null && data.getData() != null && contents != null) {
                Uri uri = data.getData();
                new Thread(() -> {
                    try (OutputStream stream = getContentResolver().openOutputStream(uri)) {
                        if (stream == null) throw new Exception("Destino indisponível");
                        stream.write(contents.getBytes(StandardCharsets.UTF_8)); runOnUiThread(() -> toast("Amostra exportada."));
                    } catch (Exception error) { runOnUiThread(() -> toast("Falha ao exportar a amostra.")); }
                }, "siopa-export").start();
            }
        }
    }
    public final class ExportBridge {
        @JavascriptInterface public void saveExport(String filename, String contents) {
            if (contents == null || contents.length() > 80 * 1024 * 1024) { runOnUiThread(() -> toast("Exportação muito grande para este aparelho.")); return; }
            runOnUiThread(() -> {
                if (!isLocal(webView.getUrl()) || pendingExport != null) return;
                pendingExport = contents;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json");
                intent.putExtra(Intent.EXTRA_TITLE, filename == null ? "siopa-amostra.json" : filename.replaceAll("[^a-zA-Z0-9._-]", "_"));
                try { startActivityForResult(intent, EXPORT); } catch (Exception error) { pendingExport = null; toast("Nenhum seletor de destino disponível."); }
            });
        }
    }
    private void toast(String message) { Toast.makeText(this, message, Toast.LENGTH_LONG).show(); }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); webView.saveState(state); }
    @Override public void onBackPressed() { if (webView.canGoBack()) webView.goBack(); else super.onBackPressed(); }
    @Override protected void onDestroy() { finishFile(null); if (locationCallback != null) locationCallback.invoke(locationOrigin, false, false); webView.removeJavascriptInterface("SiopaAndroid"); webView.destroy(); super.onDestroy(); }
}

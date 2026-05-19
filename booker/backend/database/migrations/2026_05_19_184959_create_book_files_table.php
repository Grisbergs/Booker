<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
    Schema::create('book_files', function (Blueprint $table) {
    $table->id();

    $table->foreignId('book_id')->constrained()->onDelete('cascade');

    $table->string('format');
    // epub, pdf, azw, kfx

    $table->string('file_path');
    // MinIO path

    $table->bigInteger('file_size')->nullable();

    $table->json('metadata')->nullable();
    // future: page count, drm flags, conversion info

    $table->timestamps();
});
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('book_files');
    }
};

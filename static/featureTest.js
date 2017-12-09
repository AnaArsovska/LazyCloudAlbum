$(document).ready(function(){
   //Checks to see if FormData (used in image upload) is supported. 
   try {
      var formData = new FormData();
      formData.append("test","will it work?");
      formData.has("test");
   } catch (TypeError) {
      $("#content").before("<div id='browser_warning'> This browser is not fully supported. Not all features may work as expected. </br>Please use an up-to-date version of Firefox or Chrome. </div>")
   }
});
